import asyncio
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

    return desc.NodeId.to_string()

async def act_on_node(node, parent_node, prefix=''):
    #
    for desc in await node.get_children_descriptions():
        #
        #if desc.NodeClass == ua.NodeClass.Variable:
        #    try:
        #        val = await Node(node.session, desc.NodeId).read_value()
        #    except UaStatusCodeError as err:
        #        val = "Bad (0x{0:x})".format(err.code)

        #res_list.append(print_node_description(desc))
        full_name = print_node_description(desc)
        name = full_name.split('.')[-1]
        new_node = OptNode(name, None, set(), {parent_node})
        parent_node.children.add(new_node)

        #print(prefix + name + f' : {new_node}')

        # and recurse into the child nodes
        if hasattr(node, 'session'): # newer asyncua and Python
            await act_on_node(Node(node.session, desc.NodeId), new_node, prefix+'-')
        elif hasattr(node, 'server'): # older, Python 3.6 (which is deprecated and unsafe since a few years already)
            await act_on_node(Node(node.server,  desc.NodeId), new_node, prefix+'-')
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
    opt_graph = OptNode('OPCRoot', None, set(), set())

    try:
        async with client:
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
        sys.exit(1)
    #sys.exit(0)

    return opt_graph

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Browse OPC-UA server and print all the DPs")

    dps = asyncio.run(_uals(parser))
    #dps = await _uals()

    print(f'got these: {dps}')
    for dp in dps:
        print(dp)

