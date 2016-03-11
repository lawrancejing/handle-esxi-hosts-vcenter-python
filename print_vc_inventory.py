# Following vSphere API diagram
# http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png

"""
Print the inventory of a vCenter, with:
    - list of Datacenters
    - list of Clusters per datacenter
    - list of ESXi Hosts per cluster
    - list of VMs per ESXi host
"""
def print_vc_inventory(vc_rootFolder):
    # Get list of datacenters
    datacenters = vc_rootFolder.childEntity
    print("Number of datacenters found: %d" % len(datacenters))
    for dc in datacenters:
        print("- Datacenter found with name: %s" % dc.name)
        # Get list of clusters for current datacenter
        clusters = dc.hostFolder.childEntity
        print("    Number of clusters found for DC '%s': %d" % (dc.name, len(clusters)))
        for cl in dc.hostFolder.childEntity:
            print("    - Cluster found with name: %s" % cl.name)
            # Get list of ESXi Hosts for current cluster
            hosts = cl.host
            print("        Number of ESXi Hosts found for cluster '%s': %d" % (cl.name, len(hosts)))
            for host in hosts:
                print("        - ESXi Host found with name: %s" % host.name)
                # Get list of VMs for current ESXi Host
                vms = host.vm
                print("                Number of VMs found for ESXi Host '%s': %d" % (host.name, len(vms)))
                for vm in vms:
                    print("                - VM found with name: %s" % vm.name)
