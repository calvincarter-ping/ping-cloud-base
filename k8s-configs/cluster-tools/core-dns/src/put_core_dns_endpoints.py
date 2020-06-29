import sys
import os
import boto3

r53_client = boto3.client('route53')

def get_hosted_zone_id(domain_name):
    """
    Get route 53 hosted zone id.
    """
    response = r53_client.list_hosted_zones()
    hosted_zones = response['HostedZones']
    for zones in hosted_zones:
        if zones['Name'].rstrip('.') == domain_name.rstrip('.'):
            return zones['Id'].rstrip('.')

def update_resource_record_sets(
    zone_id, action, rrs_name, rrs_type, rrs_ttl, rrs_records
):
    """
    Update route 53 hosted zone resource record sets.
    """
    return r53_client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Changes': [
                {
                    'Action': action,
                    'ResourceRecordSet': {
                        'Name': rrs_name,
                        'Type': rrs_type,
                        'TTL': rrs_ttl,
                        'ResourceRecords': [{'Value': f"\"{rrs_records}\""}],
                    },
                }
            ]
        },
    )

def main():
    """ Check endpoint config file and update Route53 """

    domain_name = os.environ.get('TENANT_DOMAIN', 'suraj.ping-demo.com.')

    try:
        with open('/config/core-dns-endpoints') as endpoint_file:
                endpoints = endpoint_file.read().strip()
        print(f"Endpoints: {endpoints}")
        if endpoints and endpoints != 'NO UPDATE':
                zone_id = get_hosted_zone_id(domain_name)
                if zone_id:
                    print(f"Updating core-dns-endpoints.{domain_name} to point to {endpoints}")
                    update_resource_record_sets(zone_id, 'UPSERT', f"core-dns-endpoints.{domain_name}", 'TXT', 60, endpoints)
                else:
                    print(f"Unable to find Hosted Zone Id for domain {domain_name}, aborting")
                    sys.exit(1)
        else:
            print(f"No update found in config file: {endpoints}, skipping")
    except FileNotFoundError:
        print('Unable to find core-dns-endpoints in /confg dir, aborting')
        sys.exit(1)
    except Exception as error:
        print(f'Error: {error}')
        sys.exit(1)

    print('Execution completed successfully.')

if __name__ == '__main__':
    main()
