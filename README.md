# Marathon External DNS services

## Overview
The marathon external DNS service searches Marathon for services that have an environment variable set called MARATHON_DNS, if it finds such a service it will create a CNAME in the appropriate zone and link that CNAME to the equivilant mesos-dns entry.

## Setup

See the docker-compose.yml for what environment variables need to be set, an explanation of each variable is noted below:

* MARATHON_URL
** The URL of the marathon server
* MESOS_DNS_DOMAIN
** The dns domain your mesos server is set to for the marathon framework, usually it's marathon.<your domain>
* CNAME_ZONE
** This is the route53 zone that you will be creating the CNAME in
* AWS_REGION
** The AWS region you're quering for route53 data
* UPDATE_INTERVAL
** How often you want to update the CNAMES, if you leave this field out it will default to 60 seconds
* AWS_ACCESS_KEY_ID
** AWS access key with the appropriate permissions
* AWS_SECRET_ACCESS_KEY
** AWS secret key with the appropriate permissions
* DRY_RUN
** Set to True if you want the script to simply output what action it would take
* DUPLICATE_ENTRY_SLACK_WEBHOOK
** This is the slack webhook that is used to notify you when there are multiple marathon applications using the same MARATHON_DNS entry

## Deployment

I run this app as a marathon service with a scale of 1.

```json
{
  "id": "marathon-external-dns",
  "cpus": 0.1,
  "mem": 128.0,
  "instances": 1,
  "container": {
    "type": "DOCKER",
    "docker": {
      "image": "jensendw/marathon_external_dns:latest"
    }
  },
  "env": {
    "AWS_REGION": "us-west-2",
    "MARATHON_URL": "http://localhost:8080",
    "MESOS_DNS_DOMAIN": "marathon.somedomain.com",
    "CNAME_ZONE": "somedomain.com",
    "UPDATE_INTERVAL": 60,
    "AWS_ACCESS_KEY_ID": "XXX",
    "AWS_SECRET_ACCESS_KEY": "YYY",
    "DUPLICATE_ENTRY_SLACK_WEBHOOK": "https://hooks.slack.com/services/xxxxxxxxx/xxxxxx/xxxxxxxxxxxxxx"
  }
}
```

You will then deploy any application you want a CNAME created for with an environment variable called MARATHON_DNS and with a value set to the CNAME record you want to create, for example if wanted to create a CNAME for tatertot.mydomain.com I would deploy my app with an ENV variable set to MARATHON_DNS=tatertot.mydomain.com
