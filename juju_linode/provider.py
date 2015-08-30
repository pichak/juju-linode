import logging
import os
import time

from juju_linode.exceptions import ConfigError, ProviderError
from juju_linode.client import Client
from juju_linode.domain_manager import DomainManager
from juju_linode.constraints import init

log = logging.getLogger("juju.linode")


def factory(config):
    cfg = Linode.get_config(config)
    ans = Linode(cfg)
    init(ans.client)
    return ans


def validate(config):
    Linode.get_config(config)


class Linode(object):

    def __init__(self, config, client=None, domain_manager=None):
        self.config = config
        if client is None:
            self.client = Client.connect(config)
        else:
            self.client = client

        if domain_manager is None:
            self.domain_manager =  DomainManager.connect(config)
        else:
            self.domain_manager =  domain_manager

    @property
    def version(self):
        return self.client.version

    @classmethod
    def get_config(cls, config):
        provider_conf = config.get_current_env_conf()
        
        if not 'linode-api-key' in provider_conf:
            raise ConfigError("Missing linode api credentials")

        if not 'linode-stack-script-id' in provider_conf:
            raise ConfigError("Missing linode stack script id")
        return provider_conf

    def get_instances(self):
        return self.client.get_linode_instaces()

    def get_instance(self, instance_id):
        return self.client.get_linode_instace(instance_id)

    def launch_instance(self, params):

        domain_postfix = params['domain_postfix']
        instance_params = {'datacenter_id': params['datacenter_id'], 'plan_id': params['plan_id']}

        # create linode Instance
        instance = self.client.create_linode_instace(**instance_params)

        # assign a domain to machine if there is domain_postfix in constraints
        if domain_postfix is not None:
            full_domain_name = instance.label+'.'+domain_postfix
            self.domain_manager.create_subdomain(full_domain_name, instance.ip_addresses[0])
            self.domain_manager.create_subdomain_alias(domain_postfix, full_domain_name, instance.label)
            instance.remote_access_name = full_domain_name
            time.sleep(30) # wait for subdomain to register on DNS servers

        # create linode disk
        disk = self.client.linode_disk_createfromstackscript(instance, self.config['linode-stack-script-id'], str(time.time()) )

        # create swap
        swap = self.client.create_linode_swap(instance)

        #create linode config
        disk_list = str(disk['DiskID']) + ',' + str(swap['DiskID'])
        self.client.create_linode_config(instance, str(time.time()), disk_list )

        # wait for all jobs before boot the linode instance
        self.wait_on(instance)

        # booting linode instance
        self.client.linode_boot(instance)

        # waiting for boot instance
        self.wait_on(instance)

        # wait for ssh service to start
        time.sleep(10)

        return instance

    def terminate_instance(self, instance_id):
        instance = self.client.get_linode_instace(instance_id)

        # shutting down instance
        self.client.linode_shutdown(instance)
        self.wait_on(instance)

        # deleting linode disks
        [self.client.delete_linode_disk(disk) for disk in self.client.get_linode_disks(instance)]
        self.wait_on(instance)

        self.client.destroy_linode_instace(instance)

    def wait_on(self, linode_instance):
        instance_pending_jobs = self.client.get_linode_pending_jobs(linode_instance)
        print('Jobs in Q: ' + str(len(instance_pending_jobs) ) )
        loop_count = 0
        while len(instance_pending_jobs) > 0:
            time.sleep(10)  # Takes on average 1m for a linode instance.
            instance_pending_jobs = self.client.get_linode_pending_jobs(linode_instance)
            print('Jobs in Q: ' + str(len(instance_pending_jobs) ) )
            if len(instance_pending_jobs) == 0:
                log.debug("Instance %s ready", linode_instance.label)
                return
            else:
                log.debug("Waiting on instance %s", linode_instance.label)
            if loop_count > 60:
                # After 10m for instance, just bail as provider error.
                raise ProviderError(
                    "Failed to get running instance %s jobs: %s" % (
                        linode_instance.label, str(instance_pending_jobs) ))
            loop_count += 1
