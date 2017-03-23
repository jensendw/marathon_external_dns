import marathon
from marathon import MarathonClient
import boto.route53
from boto.route53.record import ResourceRecordSets
import os
import time
import dns.resolver
import logging
import requests
import json

# Get necessary environment variables

MARATHON_URL = os.getenv('MARATHON_URL', 'http://localhost:8080')
MESOS_DNS_DOMAIN = os.getenv('MESOS_DNS_DOMAIN', 'some.domain.com')
CNAME_ZONE = os.getenv('CNAME_ZONE', 'mydomain.com')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
UPDATE_INTERVAL = os.getenv('UPDATE_INTERVAL', 60)
DRY_RUN = os.getenv('DRY_RUN', False)
DUPLICATE_ENTRY_SLACK_WEBHOOK = os.getenv('DUPLICATE_ENTRY_SLACK_WEBHOOK', 'https://hooks.slack.com/services/xxxxxxxxx/xxxxxx/xxxxxxxxxxxxxx')

# Convert UPDATE_INTERVAL to the correct type
UPDATE_INTERVAL = float(UPDATE_INTERVAL)
DRY_RUN = bool(DRY_RUN)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger()

def gen_mesos_dns_entry(app_id):
    appid_array = app_id[1:].split('/')
    appid_array.reverse()
    return '-'.join(appid_array) + '.' + MESOS_DNS_DOMAIN


def does_target_exist(cname, target):
    try:
        answer = dns.resolver.query(cname, "CNAME")
        for data in answer:
            if str(data.target)[:-1] == target:
                logging.info("INFO: %s already points to %s", cname, target)
                return True
            else:
                return False
    except dns.resolver.NXDOMAIN as err:
        logging.error("ERROR: Domain %s does not exist, received error: %s", cname, err)
        return False
    except dns.exception.Timeout as err:
        logging.error("ERROR: DNS operation timed out while resolving %s, received error: %s", cname, err)
        return False


def get_dns_entries(marathon_url):
    try:
        dns_entries = {}
        c = MarathonClient(marathon_url)

        for app in c.list_apps():
            if 'MARATHON_DNS' in app.env:
                logging.info("Found DNS entry: %s for application id: %s", app.env['MARATHON_DNS'], app.id)
                if app.env['MARATHON_DNS'] in dns_entries.keys():
                    logging.error("Duplicate MARATHON_DNS entry found, DNS entry: %s for ID: %s", app.env['MARATHON_DNS'], app.id)
                    logging.error("Mesos DNS entry: %s conflicts with App ID: %s", dns_entries[app.env['MARATHON_DNS']], app.id)
                    post_data = {'username': 'marathon_external_dns', 'icon_emoji': ':ghost:', 'text': 'Mesos DNS entry: {} conflicts with App ID: {}'.format(dns_entries[app.env['MARATHON_DNS']], app.id)}
                    response = requests.post(DUPLICATE_ENTRY_SLACK_WEBHOOK, data=json.dumps(post_data))
                    if response.status_code != 200:
                        logging.error("200 not received from slack, got the following response: %s", response.text)
                dns_entries[app.env['MARATHON_DNS']] = gen_mesos_dns_entry(app.id)
        return dns_entries
    except marathon.exceptions.MarathonError as err:
        logging.error("ERROR: Problem connecting to the Marathon server, received error: %s", err)


def add_route53_cname(cname, destination):
    try:
        conn = boto.route53.connect_to_region(AWS_REGION)
        zone = conn.get_zone(CNAME_ZONE)
        change_set = ResourceRecordSets(conn, zone.id)
        changes1 = change_set.add_change("UPSERT", cname, type="CNAME", ttl=60)
        changes1.add_value(destination)
        change_set.commit()
        logging.info("Updated CNAME: %s with value: %s", cname, destination)
    except boto.exception.NoAuthHandlerFound as err:
        logging.error("ERROR: Unable to authenticate to Route 53: %s", err)


def runit():
    dns_entries = get_dns_entries(MARATHON_URL)
    if dns_entries is not None:
        for key in dns_entries:
            if not does_target_exist(key, dns_entries[key]):
                if DRY_RUN is True:
                    logging.info("DRY RUN ENABLED: Would have create CNAME: %s with target %s", key, dns_entries[key])
                else:
                    add_route53_cname(key, dns_entries[key])

try:
    while True:
        dns_entries = get_dns_entries(MARATHON_URL)
        if dns_entries is not None:
            for key in dns_entries:
                if not does_target_exist(key, dns_entries[key]):
                    if DRY_RUN is True:
                        logging.info("DRY RUN ENABLED: Would have created CNAME: %s with target %s", key, dns_entries[key])
                    else:
                        add_route53_cname(key, dns_entries[key])
            time.sleep(UPDATE_INTERVAL)
        time.sleep(UPDATE_INTERVAL)
except KeyboardInterrupt:
    logging.error('interrupted!')
