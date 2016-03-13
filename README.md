# handle-esxi-hosts
Some Python modules used to handle ESXi Hosts:
- Add a standalone ESXi Host to a Cluster with vSAN enabled or not
- Move an ESXi Host from a cluster to another
- Remove an ESXi Host from the vCenter inventory

Bonus: Print out the vCenter inventory

Those moduels use pyVmomi (VMware vSphere API Python)




````python
import vcenter_helper
import handle_esxi_host
import sys

vc_details = {
    'host': '10.162.54.10',
    'user': '******',
    'pwd': '******',
}


def main(argv):
    # Establish connection with vCenter
    vc_si = vcenter_helper.create_connection_to_endpoint(
                                    ip_address=vc_details['host'],
                                    username=vc_details['user'],
                                    password=vc_details['pwd'])


    # Print vC Inventory
    vcenter_helper.print_vc_inventory(vc_serviceInstance=vc_si)
      
       
    # Move an ESXi Host from a cluster to another
    ## Get Cluster object (assuming a second cluster named 'cluster-test' got created)
    second_cluster = handle_esxi_host.get_cluster_object_from_vc(
                                 vc_serviceInstance=vc_si,
                                 target_cluster_name='cluster-test')
    ## Get Host object
    host = handle_esxi_host.get_host_object_from_vc(
                                vc_serviceInstance=vc_si,
                                target_host_name='10.145.6.172')
    ## Move the ESXi Host from its original cluster to the other cluster                            
    handle_esxi_host.move_host_to_another_cluster(
                                 host=host,
                                 dest_cluster=second_cluster)
                                 
                                 
    # Add a standalone ESXi Host to a Cluster with vSAN enabled
    handle_esxi_host.add_standalone_esxi_host(
                                vc_serviceInstance=vc_si,
                                host_ip='10.161.16.225',
                                hostUserName='root',
                                hostPassword='****',
                                dest_cluster=second_cluster,
                                cluster_vsan_enabled=True)


    # Remove an ESXi Host from the vCenter Inventory
    handle_esxi_host.remove_host_from_vc_inventory(host)


if __name__ == "__main__":
    main(sys.argv)

````
