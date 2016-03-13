# handle-esxi-hosts
Python module used to handle ESXi Host - using pyVmomi (VMware vSphere API Python)


````python
import vcenter_helper
import manage_esxi_host
import sys

vc_details = {
    'host': '10.162.54.10',
    'user': '******',
    'pwd': '******',
}

vc_cluster_name = 'cls'
vc_host_name = '10.161.16.225'


def main(argv):
    # Establish connection with vCenter
    vc_si = vcenter_helper.create_connection_to_endpoint(
                                    ip_address=vc_details['host'],
                                    username=vc_details['user'],
                                    password=vc_details['pwd'])

    # Print vC Inventory
    vcenter_helper.print_vc_inventory(vc_serviceInstance=vc_si)

    # Test Cluster object retrieval
    cluster = manage_esxi_host.get_cluster_object_from_vc(
                                vc_serviceInstance=vc_si,
                                target_cluster_name=vc_cluster_name)
    if cluster:
       print(cluster.name)
       print(len(cluster.host))




if __name__ == "__main__":
    main(sys.argv)

````
