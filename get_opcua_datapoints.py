import asyncio
from asyncua import ua
from asyncua import Node, Client #, Server
from asyncua.tools import add_minimum_args, add_common_args, parse_args, _configure_client_with_args, get_node, _lsprint_0, _lsprint_1, _lsprint_long
import sys, concurrent
from curses_menu import OptNode

#add_minimum_args(parser)

# just browse to the max depth, get the full list of all the DPs

def print_node_description(desc):
    #print(
    #    "{0} {1:30} {2!s:25} {3!s:25}".format(
    #        "> ",
    #        desc.DisplayName.to_string(),  # so, what's the datapoint?
    #        desc.NodeId.to_string(),
    #        desc.BrowseName.to_string(),
    #    )
    #)
    #print(f"{desc.NodeId.to_string()}")

    #return desc.NodeId.to_string()
    return desc.to_string()

async def act_on_node(parent_node, parent_node_opt, prefix=''):
    #
    for child_node in await parent_node.get_children():
        #print(type(child_node))
        #

        #if desc.NodeClass == ua.NodeClass.Variable:
        #    try:
        #        val = await Node(node.session, desc.NodeId).read_value()
        #    except UaStatusCodeError as err:
        #        val = "Bad (0x{0:x})".format(err.code)

        #res_list.append(print_node_description(desc))
        #desc = await child_node.read_description()
        #full_name = print_node_description(desc)
        full_name = child_node.nodeid.to_string()
        #

        # check if that's a leaf node
        next_children_nodes = await child_node.get_children()
        value = None
        #print(next_children_nodes)
        if not next_children_nodes:
            # this is a leaf node, save its value etc
            try:
                #attr = await child_node.read_attribute(ua.AttributeIds.Value)
                value = await child_node.read_value()

            #except Exception as e:
            except ua.uaerrors._auto.BadCommunicationError as e:
                #print(f'Error reading value of OPC node {child_node}', e)
                value = None

        name = full_name.split('.')[-1]
        new_opt = OptNode(name, value, set(), {parent_node_opt})

        parent_node_opt.children.add(new_opt)

        #print(prefix + name + f' : {new_opt}')

        # and recurse into the child nodes
        if hasattr(parent_node, 'session'): # newer asyncua and Python
            #await act_on_node(Node(parent_node.session, desc.NodeId), new_opt, prefix+'-')
            await act_on_node(child_node, new_opt, prefix+'-')
        elif hasattr(parent_node, 'server'): # older, Python 3.6 (which is deprecated and unsafe since a few years already)
            #await act_on_node(Node(parent_node.server,  desc.NodeId), new_opt, prefix+'-')
            await act_on_node(child_node, new_opt, prefix+'-')
        else:
            raise Exception('unknown version of asyncua')

async def _uals(parser) -> set:
    '''_uals(parser)

    parser: argparse.ArgumentParser
    returns: a list of strings with full DP names
    '''

    #parser = argparse.ArgumentParser(description="Browse OPC-UA node and print result")
    add_common_args(parser)
    parser.add_argument(
        "-l", dest="long_format", const=3, nargs="?", type=int, help="use a long listing format"
    )
    parser.add_argument("-d", "--depth", default=1, type=int, help="Browse depth")

    args = parse_args(parser)
    if args.long_format is None:
        args.long_format = 1

    client = Client(args.url, timeout=args.timeout)
    await _configure_client_with_args(client, args)

    #all_the_dps = []
    opt_graph = OptNode(args.nodeid, None, set(), set())

    try:
        async with client:
            #await client.connect()
            node = await get_node(client, args)
            print(f"Browsing node {node} at {args.url}\n")

            #if args.long_format == 0:
            #    await _lsprint_0(node, args.depth - 1)
            #elif args.long_format == 1:
            #    await _lsprint_1(node, args.depth - 1)
            #else:
            #    await _lsprint_long(node, args.depth - 1)
            # -- these print funtions do both things
            #    they browse recursively the Node tree
            #    and print the nodes info in different formats
            #    let's simply break it up

            # the problem is that all of this is done under async routines
            # so, the browsing recursion must be an async def
            await act_on_node(node, opt_graph)

    except (OSError, concurrent.futures.TimeoutError) as e:
        print(e)
        client.disconnect()
        sys.exit(1)
    #sys.exit(0)

    return opt_graph, client

async def write_opc(client, opts_lists, enter_value, logger=None):
    node_fullname = None
    try:
        async with client:
            for opt_list in opts_lists:
                node_fullname = '.'.join(n.name for n in opt_list)
                #node = await get_node(client, node_fullname)
                node = client.get_node(node_fullname)
                print(f"Browsing node {node}")
                #await act_on_node(node, opt_graph)
                if enter_value in ("true", "True", "false", "False"):
                    value = enter_value in ("true", "True")
                else:
                    value = enter_value

                await node.write_value(value)

    except (OSError, concurrent.futures.TimeoutError) as e:
        print(e)
        print(f"node {node_fullname}")
        client.disconnect()
        sys.exit(1)

    except Exception as e:
        #print(e)

        #import pdb
        #pdb.set_trace()

        raise Exception(f"node {node_fullname} client {client}") from e
        client.disconnect()
        sys,exit(2)
    #sys.exit(0)

class OpcWriteOptions:
    def __init__(self, opc_client, next_prog=None):
        self.opc_client = opc_client
        self.next_prog = next_prog
        
    def __call__(self, cscreen, opts_lists=[], enter_str='', logger=None):
        logger.debug('OpcWriteOptions')
        asyncio.run(write_opc(self.opc_client, opts_lists, enter_str, logger))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Browse OPC-UA server and print all the DPs")

    dps, client = asyncio.run(_uals(parser))
    #dps = await _uals()

    opts_lists = dps.opt_list()

    print(f'got these: {dps}')
    for optlist in opts_lists:
        #print([(i.name, i.value) for i in optlist])
        print([(i.name, i.value) for i in optlist])

