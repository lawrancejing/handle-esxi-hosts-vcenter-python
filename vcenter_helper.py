from pyVim import connect
import ssl

# Following vSphere API diagram
# http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png

"""
Create a connection to vCenter or an ESXi Host by using the endpoint IP Address and a set of credentials
-> returns the ServiceInstance object
"""
def create_connection_to_endpoint(ip_address, username, password):
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE
        si = connect.SmartConnect(host=ip_address,
                                  user=username,
                                  pwd=password,
                                  sslContext=context)
        return si
    except IOError, ex:
        raise SystemExit("Unable to connect to host with supplied info.")


"""
Print the inventory of a vCenter, with:
    - list of Datacenters
    - list of Clusters per datacenter
    - list of ESXi Hosts per cluster
    - list of VMs per ESXi host
    - list of Datastores per datacenter
"""
def print_vc_inventory(vc_serviceInstance):
    vc_rootFolder = vc_serviceInstance.RetrieveContent().rootFolder
    # Get list of datacenters
    datacenters = vc_rootFolder.childEntity
    print("Number of datacenters found: %d" % len(datacenters))
    for dc in datacenters:
        print("- Datacenter found with name: %s" % dc.name)
        # Get list of clusters for current datacenter
        clusters = dc.hostFolder.childEntity
        print("    Number of clusters found for DC '%s': %d" % (dc.name, len(clusters)))
        for cl in clusters:
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
        # Get list of Datastores for current datacenter
        datastores = dc.datastoreFolder.childEntity
        print("")
        print("    Number of datastores found for DC '%s': %d" % (dc.name, len(datastores)))
        for ds in datastores:
            print("        + Datastore found with name: %s" % ds.name)

