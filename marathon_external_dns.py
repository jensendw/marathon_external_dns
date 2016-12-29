from marathon import MarathonClient
import boto.route53
from boto.route53.record import ResourceRecordSets
import os
import time

# Get necessary environment variables

MARATHON_URL = os.getenv('MARATHON_URL', 'http://localhost:8080')
MESOS_DNS_DOMAIN = os.getenv('MESOS_DNS_DOMAIN', 'some.domain.com')
CNAME_ZONE = os.getenv('CNAME_ZONE', 'mydomain.com')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
UPDATE_INTERVAL = os.getenv('UPDATE_INTERVAL', 60)

# Convert UPDATE_INTERVAL to the correct type
UPDATE_INTERVAL = float(UPDATE_INTERVAL)


def gen_mesos_dns_entry(app_id):
    return app_id[1:].replace('/', '-') + '.' + MESOS_DNS_DOMAIN


def get_dns_entries(marathon_url):
    dns_entries = {}
    c = MarathonClient(marathon_url)

    for app in c.list_apps():
        if 'MARATHON_DNS' in app.env:
            print "Found DNS entry: %s for application id: %s" % (app.env['MARATHON_DNS'], app.id)
            dns_entries[app.env['MARATHON_DNS']] = gen_mesos_dns_entry(app.id)
    return dns_entries


def add_route53_cname(cname, destination):
    conn = boto.route53.connect_to_region(AWS_REGION)
    zone = conn.get_zone(CNAME_ZONE)
    change_set = ResourceRecordSets(conn, zone.id)
    changes1 = change_set.add_change("UPSERT", cname, type="CNAME", ttl=60)
    changes1.add_value(destination)
    change_set.commit()
    print "Updated CNAME: %s with value: %s" % (cname, destination)

while True:
    dns_entries = get_dns_entries(MARATHON_URL)
    for key in dns_entries:
        add_route53_cname(key, dns_entries[key])
    time.sleep(UPDATE_INTERVAL)
