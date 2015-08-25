import logging
import os
import time

from juju_linode.exceptions import ConfigError, ProviderError
from juju_linode.client import Client
from juju_linode.constraints import init

log = logging.getLogger("juju.linode")


def factory():
    cfg = Linode.get_config()
    ans = Linode(cfg)
    init(ans.client)
    return ans


def validate():
    Linode.get_config()


class Linode(object):

    def __init__(self, config, client=None):
        self.config = config
        if client is None:
            self.client = Client.connect(config)
        else:
            self.client = client

    @property
    def version(self):
        return self.client.version

    @classmethod
    def get_config(cls):
        provider_conf = {}

        api_key = os.environ.get('LINODE_API_KEY')
        if api_key:
            provider_conf['LINODE_API_KEY'] = api_key

        stack_script_id = os.environ.get('LINODE_STACK_SCRIPT_ID')
        if api_key:
            provider_conf['LINODE_STACK_SCRIPT_ID'] = stack_script_id

        if not 'LINODE_API_KEY' in provider_conf:
            raise ConfigError("Missing linode api credentials")

        if not 'LINODE_STACK_SCRIPT_ID' in provider_conf:
            raise ConfigError("Missing linode stack script id")
        return provider_conf

    def get_instances(self):
        return self.client.get_linode_instaces()

    def get_instance(self, instance_id):
        return self.client.get_linode_instace(instance_id)

    def launch_instance(self, params):
        # create linode Instance
        instance = self.client.create_linode_instace(**params)

        # create linode disk
        disk = self.client.linode_disk_createfromstackscript(instance, self.config['LINODE_STACK_SCRIPT_ID'], str(time.time()) )

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
