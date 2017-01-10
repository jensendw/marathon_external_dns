import marathon
from marathon import MarathonClient
import boto.route53
from boto.route53.record import ResourceRecordSets
import os
import time
import dns.resolver
import sys


# Get necessary environment variables

MARATHON_URL = os.getenv('MARATHON_URL', 'http://localhost:8080')
MESOS_DNS_DOMAIN = os.getenv('MESOS_DNS_DOMAIN', 'some.domain.com')
CNAME_ZONE = os.getenv('CNAME_ZONE', 'mydomain.com')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
UPDATE_INTERVAL = os.getenv('UPDATE_INTERVAL', 60)
DRY_RUN = os.getenv('DRY_RUN', False)

# Convert UPDATE_INTERVAL to the correct type
UPDATE_INTERVAL = float(UPDATE_INTERVAL)
DRY_RUN = bool(DRY_RUN)


def gen_mesos_dns_entry(app_id):
    appid_array = app_id[1:].split('/')
    appid_array.reverse()
    return '-'.join(appid_array) + '.' + MESOS_DNS_DOMAIN


def does_target_exist(cname, target):
    try:
        answer = dns.resolver.query(cname, "CNAME")
        for data in answer:
            if str(data.target)[:-1] == target:
                print "INFO: %s already points to %s" % (cname, target)
                return True
            else:
                return False
    except dns.resolver.NXDOMAIN as err:
        print "ERROR: Domain %s does not exist, received error: %s" % (cname, err)
        return False
    except dns.exception.Timeout as err:
        print "ERROR: DNS operation timed out while resolving %s, received error: %s" % (cname, err)
        return False


def get_dns_entries(marathon_url):
    try:
        dns_entries = {}
        c = MarathonClient(marathon_url)

        for app in c.list_apps():
            if 'MARATHON_DNS' in app.env:
                print "Found DNS entry: %s for application id: %s" % (app.env['MARATHON_DNS'], app.id)
                dns_entries[app.env['MARATHON_DNS']] = gen_mesos_dns_entry(app.id)
        return dns_entries
    except marathon.exceptions.MarathonError as err:
        print "ERROR: Problem connecting to the Marathon server, received error: %s" % (err)


def add_route53_cname(cname, destination):
    try:
        conn = boto.route53.connect_to_region(AWS_REGION)
        zone = conn.get_zone(CNAME_ZONE)
        change_set = ResourceRecordSets(conn, zone.id)
        changes1 = change_set.add_change("UPSERT", cname, type="CNAME", ttl=60)
        changes1.add_value(destination)
        change_set.commit()
        print "Updated CNAME: %s with value: %s" % (cname, destination)
    except boto.exception.NoAuthHandlerFound as err:
        print "ERROR: Unable to authenticate to Route 53: %s" % (err)


def runit():
    dns_entries = get_dns_entries(MARATHON_URL)
    if dns_entries is not None:
        for key in dns_entries:
            if not does_target_exist(key, dns_entries[key]):
                if DRY_RUN is True:
                    print "DRY RUN ENABLED: Would have create CNAME: %s with target %s" % (key, dns_entries[key])
                else:
                    add_route53_cname(key, dns_entries[key])

try:
    while True:
        dns_entries = get_dns_entries(MARATHON_URL)
        if dns_entries is not None:
            for key in dns_entries:
                if not does_target_exist(key, dns_entries[key]):
                    if DRY_RUN is True:
                        print "DRY RUN ENABLED: Would have create CNAME: %s with target %s" % (key, dns_entries[key])
                    else:
                        add_route53_cname(key, dns_entries[key])
            time.sleep(UPDATE_INTERVAL)
        time.sleep(UPDATE_INTERVAL)
except KeyboardInterrupt:
    print 'interrupted!'
