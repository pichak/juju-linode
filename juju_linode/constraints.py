from juju_linode.exceptions import ConstraintError

DEFAULT_DATACENTER = '2'
DATACENTERS = ()
DEFAULT_PLAN = '1'
PLAN_MAP = ()

# Would be nice to use ubuntu-distro-info, but portability.
SERIES_MAP = {
    '12-04': 'precise',
    '14-04': 'trusty'}

ARCHES = ['amd64']

# afaics, these are unavailable
#
#    {'name': 'Amsterdam 1 1', 'aliases': ['ams1']

SUFFIX_SIZES = {
    "m": 1,
    "g": 1024,
    "t": 1024 * 1024,
    "p": 1024 * 1024 * 1024}


def init(client, data=None):
    global PLAN_MAP, DATACENTERS, DEFAULT_DATACENTER

    if data is not None:
        PLAN_MAP = data['plans']
        DATACENTERS = data['datacenters']
        return

    PLAN_MAP = client.get_linode_plans()
    for plan in PLAN_MAP:
        if plan.label == 'Linode 1024':
            DEFAULT_PLAN = plan.planid
            break
    else:
        raise ValueError("Could not find plan 'Linode 1024'")

    # Record datacenters so we can offer nice aliases.
    DATACENTERS = client.get_datacenters()

    for datacenter in DATACENTERS:
        if datacenter.abbr == 'dallas':
            DEFAULT_DATACENTER = datacenter.datacenterid
            break
    else:
        raise ValueError("Could not find region 'dallas'")


def parse_constraints(constraints):
    """
    """
    c = {}
    parts = filter(None, constraints.split(","))
    for p in parts:
        k, v = p.split('=', 1)
        c[k.strip()] = v.strip()

    unknown = set(c).difference(
        set(['datacenter', 'plan']))
    if unknown:
        raise ConstraintError("Unknown constraints %s" % (" ".join(unknown)))

    c_out = {}
    
    if 'plan' in c:
        for p in PLAN_MAP:
            if c['plan'].lower() == p.label.lower() or 'linode '+c['plan'].lower() == p.label.lower(): # both "1024" and "linode 1024" is acceptable
                c_out['plan'] = p.planid
                break
        else:
            raise ConstraintError("Unknown Linode plan %s" % c['plan'])

    if 'datacenter' in c:
        for d in DATACENTERS:
            if c['datacenter'] == d.abbr:
                c_out['datacenter'] = d.datacenterid
                break
        else:
            raise ConstraintError("Unknown datacenter %s" % c['datacenter'])

    return c_out


def solve_constraints(constraints):
    """Return machine plan and datacenter.
    """

    constraints = parse_constraints(constraints)
    constraints['datacenter'] = constraints.pop('datacenter', DEFAULT_DATACENTER)
    constraints['plan'] = constraints.pop('plan', DEFAULT_PLAN)
    print(constraints)

    return constraints['plan'], constraints['datacenter']


def get_images(client):
    images = {}
    for i in client.get_images():
        if not i.public:
            continue
        if not i.distribution == "Ubuntu":
            continue

        for s in SERIES_MAP:
            if ("ubuntu-%s-x64" % s) == i.slug:
                images[SERIES_MAP[s]] = i.id
                images[s.replace('-', '.')] = i.id
    return images
