#!/usr/bin/env python
"""Generate diagrams from imposm mapping schema and tm2source project.
Usage:
  generate_diagram.py mapping-keys <mapping_file>
  generate_diagram.py mapping-layers <tm2source_file> <mapping_file>
  generate_diagram.py layers <tm2source_file> [--individual]
  generate_diagram.py (-h | --help)
  generate_diagram.py --version
Options:
  -h --help         Show this screen.
  --version         Show version.
  --individual      Render each layer into separate file
"""
import re
from collections import namedtuple

from docopt import docopt
from graphviz import Digraph
import yaml


Layer = namedtuple('Layer', ['name', 'referenced_tables', 'fields'])
Table = namedtuple('Table', ['name', 'fields', 'mapping', 'type'])


def values_label(osm_values):
    return '[{} values]'.format(len(osm_values))


def normalize_graphviz_labels(label):
    return label.replace(':', '_')


def generate_mapping_subgraph(table):
    subgraph = Digraph(table.name, node_attr={
        'width:': '20',
        'fixed_size': 'shape'
    })

    subgraph.node(table.name, shape='box')

    for osm_key, osm_values in table.mapping:
        node_name = 'key_' + normalize_graphviz_labels(osm_key)
        subgraph.node(node_name, label=osm_key, shape='box')

        subgraph.edge(node_name, table.name,
                      label=values_label(osm_values), )

    return subgraph


def find_referenced_tables(sql_cmd, table_prefix="osm"):
    """Find all tables used in SQL FROM statements"""

    regexpr = "FROM {}_(\w*)".format(table_prefix)
    table_regex = re.compile(regexpr, re.IGNORECASE)
    for match in table_regex.findall(sql_cmd):
        yield replace_generalization_postfix(match)


def replace_generalization_postfix(table_name):
    return table_name.replace('_gen0', '').replace('_gen1', '')


def merge_grouped_mappings(mappings):
    """Merge multiple mappings into a single mapping for drawing"""
    for mapping_group, mapping_value in mappings.items():
        yield mapping_group, mapping_value['mapping']


def find_tables(config):
    for table_name, table_value in config['tables'].items():
        fields = table_value.get('fields')

        if table_value.get('mappings'):
            mapping = list(merge_grouped_mappings(table_value['mappings']))
        else:
            mapping = table_value.get('mapping').items()

        if mapping and fields:
            yield Table(table_name, fields, mapping, table_value['type'])


def find_layers(config):
    for layer in config['Layer']:
        layer_name = layer['id']
        sql_cmd = layer['Datasource']['table']

        tables = set([t for t in find_referenced_tables(sql_cmd)])

        fields = layer['fields'].items()
        yield Layer(layer_name, tables, fields)


def generate_struct_diagram(heading, body):
    return '''<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
  <TR>
    <TD BGCOLOR="#EEEEEE">{0}</TD>
  </TR>
  <TR>
    <TD>{1}</TD>
  </TR>
</TABLE>>'''.format(heading, body)


def generate_table_node(graph, table):
    field_names = [field['name'] for field in table.fields]
    node_body = generate_struct_diagram(
        table.name,
        '<BR/>'.join(field_names)
    )
    node_name = 'table_' + table.name
    graph.node(node_name, node_body, shape='none')
    return node_name


def generate_layer_node(graph, layer):
    field_names = sorted(['{}: {}'.format(field_name, field_type)
                          for field_name, field_type in layer.fields])

    node_body = generate_struct_diagram(
        '#' + layer.name,
        '<BR/>'.join(field_names)
    )
    node_name = 'layer_' + layer.name
    graph.node(node_name, node_body, shape='none')
    return node_name


def generate_table_layer_diagram(mapping_config, tm2source_config):
    graph = Digraph('Layers from Table Mappings', format='png', graph_attr={
        'rankdir': 'LR'
    })

    layers = find_layers(tm2source_config)
    tables = find_tables(mapping_config)

    for table in tables:
        generate_table_node(graph, table)

    for layer in layers:
        layer_node = generate_layer_node(graph, layer)
        for table_name in layer.referenced_tables:
            graph.edge('table_' + table_name, layer_node)

    graph.render(filename='table_layer_diagram', view=True)


def generate_layer_diagram(tm2source_config, individual):

    def make_graph():
        return Digraph('Layers', format='png', graph_attr={
            'rankdir': 'LR'
        })

    layers = find_layers(tm2source_config)

    if individual:
        for layer in layers:
            graph = make_graph()
            generate_layer_node(graph, layer)
            graph.render(filename='layer_' + layer.name, view=False)
    else:
        graph = make_graph()
        for layer in layers:
            generate_layer_node(graph, layer)
        graph.render(filename='layers', view=True)


def generate_table_mapping_diagram(mapping_config):
    graph = Digraph('Imposm Mapping', format='png', graph_attr={
        'rankdir': 'LR',
        'ranksep': '3'
    })

    for table in find_tables(mapping_config):
        graph.subgraph(generate_mapping_subgraph(table))

    graph.render(filename='mapping_graph', view=True)


if __name__ == '__main__':
    args = docopt(__doc__, version='0.1')
    mapping_file = args.get('<mapping_file>')
    tm2source_file = args.get('<tm2source_file>')

    if args.get('layers'):
        tm2source_config = yaml.load(open(tm2source_file, 'r'))
        generate_layer_diagram(tm2source_config,
                               individual=args.get('--individual'))

    if args.get('mapping-layers'):
        mapping_config = yaml.load(open(mapping_file, 'r'))
        tm2source_config = yaml.load(open(tm2source_file, 'r'))
        generate_table_layer_diagram(mapping_config, tm2source_config)

    if args.get('mapping-keys'):
        mapping_config = yaml.load(open(mapping_file, 'r'))
        generate_table_mapping_diagram(mapping_config)
