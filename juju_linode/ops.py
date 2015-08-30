import logging
import subprocess
import time
import uuid


from juju_linode.exceptions import TimeoutError, ProviderAPIError
from juju_linode import ssh, constraints


log = logging.getLogger("juju.linode")


class MachineOp(object):

    def __init__(self, provider, env, params, **options):
        self.provider = provider
        self.env = env
        self.params = params
        self.created = time.time()
        self.options = options

    def run(self):
        raise NotImplementedError()


class MachineAdd(MachineOp):

    def run(self):
        instance = self.provider.launch_instance(self.params)
        return instance

class MachineRegister(MachineAdd):

    def run(self):
        instance = super(MachineRegister, self).run()
        try:
            machine_id = self.env.add_machine(
                "ssh:ubuntu@%s" % instance.remote_access_name)
        except:
            self.provider.terminate_instance(instance.linodeid)
            raise
        return instance, machine_id


class MachineDestroy(MachineOp):

    def run(self):
        if not self.options.get('iaas_only'):
            self.env.terminate_machines([self.params['machine_id']])
        if self.options.get('env_only'):
            return
        log.debug("Destroying instance %s", self.params['instance_id'])
        while True:
            try:
                self.provider.terminate_instance(self.params['instance_id'])
                break
            except ProviderAPIError, e:
                # The vm has a pending event, sleep and try again.
                if e.message['id'] == 'unprocessable_entity':
                    log.debug(
                        "Waiting for pending instance action to complete.")
                    time.sleep(6)
                    continue
                raise
            break
