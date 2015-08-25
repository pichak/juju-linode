import logging
import time
import uuid
import yaml

from juju_linode import constraints
from juju_linode.exceptions import ConfigError, PrecheckError
from juju_linode import ops
from juju_linode.runner import Runner


log = logging.getLogger("juju.linode")


class BaseCommand(object):

    def __init__(self, config, provider, environment):
        self.config = config
        self.provider = provider
        self.env = environment
        self.runner = Runner()

    def solve_constraints(self):
        return constraints.solve_constraints(self.config.constraints)
        
    def get_linode_ssh_keys(self):
        return [k.id for k in self.provider.get_ssh_keys()]

    def check_preconditions(self):
        """Check for provider ssh key, and configured environments.yaml.
        """
        env_name = self.config.get_env_name()
        with open(self.config.get_env_conf()) as fh:
            conf = yaml.safe_load(fh.read())
            if not 'environments' in conf:
                raise ConfigError(
                    "Invalid environments.yaml, no 'environments' section")
            if not env_name in conf['environments']:
                raise ConfigError(
                    "Environment %r not in environments.yaml" % env_name)
            env = conf['environments'][env_name]
            if not env['type'] in ('null', 'manual'):
                raise ConfigError(
                    "Environment %r provider type is %r must be 'null'" % (
                        env_name, env['type']))
            if env['bootstrap-host']:
                raise ConfigError(
                    "Environment %r already has a bootstrap-host" % (
                        env_name))


class Bootstrap(BaseCommand):
    """
    Actions:
    - Launch an instance
    - Wait for it to reach running state
    - Update environment in environments.yaml with bootstrap-host address.
    - Bootstrap juju environment

    Preconditions:
    - named environment found in environments.yaml
    - environment provider type is null
    - bootstrap-host must be null
    - at least one ssh key must exist.
    - ? existing linode with matching env name does not exist.
    """
    def run(self):
        self.check_preconditions()
        plan, datacenter = self.solve_constraints()
        log.info("Launching bootstrap host (eta 5m)...")
        params = dict(datacenter_id=datacenter, plan_id=plan)

        op = ops.MachineAdd(
            self.provider, self.env, params)
        instance = op.run()

        log.info("Bootstrapping environment...")
        try:
            self.env.bootstrap_jenv(instance.ip_addresses[0])
        except:
            self.provider.terminate_instance(instance.linodeid)
            raise
        log.info("Bootstrap complete.")

    def check_preconditions(self):
        super(Bootstrap, self).check_preconditions()
        if self.env.is_running():
            raise PrecheckError(
                "Environment %s is already bootstrapped" % (
                self.config.get_env_name()))


class ListMachines(BaseCommand):

    def run(self):
        env_name = self.config.get_env_name()
        header = "{:<8} {:<18} {:<5} {:<10} {:<20}".format(
            "Id", "Label", "RAM", "DataCenter", "Address")

        allmachines = self.config.options.all
        for m in self.provider.get_instances():
            if not allmachines and not m.name.startswith('%s-' % env_name):
                continue

            if header:
                print(header)
                header = None

            for d in constraints.DATACENTERS:
                if m.datacenterid == d.datacenterid:
                    break
            name = m.name
            if len(name) > 18:
                name = name[:15] + "..."
            
            print("{:<8} {:<18} {:<5} {:<10} {:<20}".format(
                m.id,
                m.label,
                m.totalram,
                d.abbr,
                ','.join(m.ip_addresses) ).strip())


class AddMachine(BaseCommand):

    def run(self):
        self.check_preconditions()
        plan, datacenter = self.solve_constraints()
        log.info("Launching %d instances...", self.config.num_machines)

        params = dict(datacenter_id=datacenter, plan_id=plan)

        op_class = ops.MachineRegister

        for n in range(self.config.num_machines):
            self.runner.queue_op(
                op_class(
                    self.provider, self.env, params))

        for result in self.runner.iter_results():
            pass


class TerminateMachine(BaseCommand):

    def run(self):
        """Terminate machine in environment.
        """
        self.check_preconditions()
        self._terminate_machines()

    def _machine_filter(self, mid, m):
        return any([
            spec == mid for spec in
            self.config.options.machines if mid != '0'])

    def _terminate_machines(self, machine_filter=None):
        status = self.env.status()
        machines = status.get('machines', {})

        machine_filter = machine_filter or self._machine_filter
        # Using the api instance-id can be the provider id, but
        # else it defaults to ip, and we have to disambiguate.
        remove = []
        for m in machines:
            if machine_filter(m, machines[m]):
                remove.append(
                    {'address': machines[m].get('dns-name'),
                     'instance_id': machines[m]['instance-id'],
                     'machine_id': m})

        address_map = dict([(d.ip_addresses[0], d) for
                            d in self.provider.get_instances()])
        if not remove:
            return status, address_map

        log.info("Terminating machines %s",
                 " ".join([m['machine_id'] for m in remove]))

        for m in remove:
            instance = None
            if m['address']:
                instance = address_map.get(m['address'])
            else:
                instances = [
                    i for i in address_map.values()
                    if m['instance_id'] == i.name]
                if len(instances) == 1:
                    instance = instances[0]
                    #instances['instance'] =
            env_only = False  # Remove from only env or also provider.
            if instance is None:
                log.warning(
                    "Couldn't resolve machine %s's address %s to instance" % (
                        m['machine_id'], m['address']))
                # We have a machine in juju state that we couldn't
                # find in provider. Remove it from state so destroy
                # can proceed.
                env_only = True
                instance_id = None
            else:
                instance_id = instance.linodeid
            self.runner.queue_op(
                ops.MachineDestroy(
                    self.provider, self.env, {
                        'machine_id': m['machine_id'],
                        'instance_id': instance_id},
                    env_only=env_only))
        for result in self.runner.iter_results():
            pass

        return status, address_map


class DestroyEnvironment(TerminateMachine):

    def run(self):
        """Destroy environment.
        """
        self.check_preconditions()
        force = self.config.options.force

        # Manual provider needs machines removed prior to env destroy.
        def state_service_filter(mid, m):
            if mid == "0":
                return False
            return True

        if force:
            return self.force_environment_destroy()

        env_status, instance_map = self._terminate_machines(
            state_service_filter)

        # sadness, machines are marked dead, but juju is async to
        # reality. either sleep (racy) or retry loop, 10s seems to
        # plenty of time.
        time.sleep(10)

        log.info("Destroying environment")
        self.env.destroy_environment()

        # Remove the state server.
        bootstrap_host = env_status.get(
            'machines', {}).get('0', {}).get('dns-name')
        instance = instance_map.get(bootstrap_host)
        if instance:
            log.info("Terminating state server")
            self.provider.terminate_instance(instance.linodeid)
        log.info("Environment Destroyed")

    def force_environment_destroy(self):
        env_name = self.config.get_env_name()
        env_machines = [m for m in self.provider.get_instances()
                        if m.name.startswith("%s-" % env_name)]

        log.info("Destroying environment")
        for m in env_machines:
            self.runner.queue_op(
                ops.MachineDestroy(
                    self.provider, self.env, {'instance_id': m.id},
                    iaas_only=True))

        for result in self.runner.iter_results():
            pass

        # Fast destroy the client cache by removing the jenv file.
        self.env.destroy_environment_jenv()
        log.info("Environment Destroyed")
