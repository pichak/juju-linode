from juju_linode.exceptions import ProviderAPIError

import requests

import random

import string


class Entity(object):

    @classmethod
    def from_dict(cls, data):
        i = cls()
        i.__dict__.update(data)
        i.json_keys = data.keys()
        return i

    def to_json(self):
        return dict([(k, getattr(self, k)) for k in self.json_keys])


class LinodeInstace(Entity):
    """Instance on linode.

    Attributes: alert_cpu_enabled, alert_bwin_enabled, alert_bwquota_enabled, alert_diskio_threshold,
        backupwindow, watchdog, distributionvendor, datacenterid, status, alert_diskio_enabled, create_dt,
        totalhd, alert_bwquota_threshold, totalram, alert_bwin_threshold, linodeid, alert_bwout_threshold,
        alert_bwout_enabled, backupsenabled, alert_cpu_threshold, planid, backupweeklyday, label, lpm_displaygroup,
        totalxfer
    """


class Distribution(Entity):
    """
    Attributes: distributionid, is64bit, requirespvopskernel, label, minimagesize, create_dt
    """

class DataCenter(Entity):
    """
    Attributes: datacenterid, abbr, location
    """

class Plan(Entity):
    """
    Attributes: cores, price, ram, xfer, planid, label, avail, disk, hourly
    """

class Disk(Entity):
    """
    Attributes: update_dt, diskid, label, type, linodeid, isreadonly, create_dt, size
    """

class Job(Entity):
    """
    Attributes: entered_dt, action, label, host_start_dt, linodeid, host_finish_dt, duration, host_message, jobid, host_success
    """



class Client(object):

    version = 1.0

    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url_base = 'https://api.linode.com'

    def request(self, api_action, params=None, method='GET'):
        p = params and dict(params) or {}
        p['api_key'] = self.api_key
        p['api_action'] = api_action

        print("Action: " + api_action)
        print("Params: " + str(params))

        # remove null values
        p = {k: v for k, v in p.items() if v}

        headers = {'User-Agent': 'juju/client'}
        url = self.api_url_base

        if method == 'POST':
            headers['Content-Type'] = "application/json"
            response = requests.post(url, headers=headers, params=p)
        else:
            response = requests.get(url, headers=headers, params=p)

        data = response.json()
        if not data:
            raise ProviderAPIError('No json result found')

        if len(data['ERRORARRAY']) != 0:
            raise ProviderAPIError(data['ERRORARRAY'])

        return data['DATA']


    def make_datacenters(self, info):
        return DataCenter.from_dict(
            dict(datacenterid=info['DATACENTERID'], abbr=info['ABBR'], location=info['LOCATION']))

    def get_datacenters(self):
        data = self.request("avail.datacenters")
        return map(self.make_datacenters, data)

    def make_plans(self, info):
        return Plan.from_dict(
            dict(cores=info['CORES'], price=info['PRICE'], ram=info['RAM'],
                xfer=info['XFER'], planid=info['PLANID'], label=info['LABEL'],
                avail=info['AVAIL'], disk=info['DISK'], hourly=info['HOURLY']))

    def get_linode_plans(self):
        data = self.request("avail.linodeplans")
        return map(self.make_plans, data)

    def make_distribution(self, info):
        return Distribution.from_dict(
            dict(distributionid=info['DISTRIBUTIONID'], is64bit=info['IS64BIT'], requirespvopskernel=info['REQUIRESPVOPSKERNEL'],
                 label=info['LABEL'], minimagesize=info['MINIMAGESIZE'],
                 create_dt=info['CREATE_DT']))

    def get_distributions(self):
        data = self.request("avail.distributions")
        return map(self.make_distribution, data)

    def make_linode_instace(self, info):
        ip_addresses = [ip_field['IPADDRESS'] for ip_field in self.request("linode.ip.list", {'LinodeID': info['LINODEID']})]
        return LinodeInstace.from_dict(
            dict(alert_cpu_enabled=info['ALERT_CPU_ENABLED'], alert_bwin_enabled=info['ALERT_BWIN_ENABLED'], alert_bwquota_enabled=info['ALERT_BWQUOTA_ENABLED'],
                 alert_diskio_threshold=info['ALERT_DISKIO_THRESHOLD'], backupwindow=info['BACKUPWINDOW'],watchdog=info['WATCHDOG'],
                 distributionvendor=info['DISTRIBUTIONVENDOR'], datacenterid=info['DATACENTERID'], status=info['STATUS'],
                 alert_diskio_enabled=info['ALERT_DISKIO_ENABLED'], create_dt=info['CREATE_DT'], totalhd=info['TOTALHD'],
                 alert_bwquota_threshold=info['ALERT_BWQUOTA_THRESHOLD'], totalram=info['TOTALRAM'],alert_bwin_threshold=info['ALERT_BWIN_THRESHOLD'],
                 linodeid=info['LINODEID'], alert_bwout_threshold=info['ALERT_BWOUT_THRESHOLD'],alert_bwout_enabled=info['ALERT_BWOUT_ENABLED'],
                 backupsenabled=info['BACKUPSENABLED'], alert_cpu_threshold=info['ALERT_CPU_THRESHOLD'], planid=info['PLANID'],
                 backupweeklyday=info['BACKUPWEEKLYDAY'], label=info['LABEL'],lpm_displaygroup=info['LPM_DISPLAYGROUP'],
                 totalxfer=info['TOTALXFER'], ip_addresses=ip_addresses, remote_access_name=ip_addresses[0]) )

    def get_linode_instaces(self):
        data = self.request("linode.list")
        return map(self.make_linode_instace, data)

    def get_linode_instace(self, linode_instace_id):
        data = self.request("linode.list", {'LinodeID': linode_instace_id})

        return self.make_linode_instace(data[0] if len(data) > 0 else {})

    def create_linode_instace(self, datacenter_id, plan_id, payment_term=None):
        params = dict(DatacenterID=datacenter_id, PlanID=plan_id, PaymentTerm=payment_term)
        data = self.request('linode.create', params)

        return self.get_linode_instace(data['LinodeID'])

    def get_random_pass(self):
        N = 3;
        password = ''.join(random.choice(string.ascii_uppercase) for _ in range(N))
        password += ''.join(random.choice(string.ascii_lowercase) for _ in range(N))
        password += ''.join(random.choice(string.digits) for _ in range(N))
        password += ''.join(random.choice('!@#$%^&*') for _ in range(N))
        return ''.join(random.sample(password,len(password)))

    def linode_disk_createfromstackscript(
        self, linode_instace, stack_script_id, label, size=None, stack_script_udf_responses={},
        distribution_id=124, root_pass=None, root_ssh_key=None):

        if not root_pass:
            root_pass = self.get_random_pass()

        if not size:
            size = linode_instace.planid * 24320

        params = dict(
            LinodeID=linode_instace.linodeid,
            StackScriptID=stack_script_id,
            Label=label,
            Size=size,
            StackScriptUDFResponses=str(stack_script_udf_responses),
            DistributionID=distribution_id,
            rootPass=root_pass,
            rootSSHKey=root_ssh_key)

        return self.request('linode.disk.createfromstackscript', params)

    def create_linode_swap(self, linode_instace, size=None):
        if not size:
            size = linode_instace.planid * 256

        params = dict(
            LinodeID=linode_instace.linodeid,
            Type='swap',
            Label='swap',
            Size=size)

        return self.request('linode.disk.create', params)

    def make_linode_disk(self, info):
        return Disk.from_dict(
            dict(update_dt=info['UPDATE_DT'], diskid=info['DISKID'], label=info['LABEL'],
                type=info['TYPE'], linodeid=info['LINODEID'], isreadonly=info['ISREADONLY'],
                create_dt=info['CREATE_DT'], size=info['SIZE']) )

    def get_linode_disks(self, linode_instace):
        data = self.request('linode.disk.list', {'LinodeID': linode_instace.linodeid})
        return map(self.make_linode_disk, data)

    def create_linode_config(self, linode_instace, label, disk_list, kernel_id=199):
        params = dict(
            LinodeID=linode_instace.linodeid,
            Label=label,
            DiskList=disk_list,
            KernelID=kernel_id)

        return self.request('linode.config.create', params)

    def linode_boot(self, linode_instace):
        return self.request('linode.boot', {'LinodeID': linode_instace.linodeid})

    def linode_shutdown(self, linode_instace):
        return self.request('linode.shutdown', {'LinodeID': linode_instace.linodeid})

    def delete_linode_disk(self, disk):
        return self.request('linode.disk.delete', {'LinodeID': disk.linodeid, 'DiskID': disk.diskid})

    def destroy_linode_instace(self, linode_instace):
        return self.request('linode.delete', {'LinodeID': linode_instace.linodeid})

    def make_linode_job(self, info):
        return Job.from_dict(
            dict(entered_dt=info['ENTERED_DT'], action=info['ACTION'], label=info['LABEL'],
                host_start_dt=info['HOST_START_DT'], linodeid=info['LINODEID'], host_finish_dt=info['HOST_FINISH_DT'],
                duration=info['DURATION'], host_message=info['HOST_MESSAGE'], jobid=info['JOBID'], host_success=info['HOST_SUCCESS']) )

    def get_linode_pending_jobs(self, linode_instace):
        data = self.request('linode.job.list', {'LinodeID': linode_instace.linodeid, 'pendingOnly': '1'})
        return map(self.make_linode_job, data)


    @classmethod
    def connect(cls, config):
        key = config.get('linode-api-key')
        if not key:
            raise KeyError("Missing api credentials")
        else:
            return Client(key)




def main():
    import code
    client = Client.connect()
    code.interact(local={'client': client})


if __name__ == '__main__':
    main()
