import argparse
import ast
import sys

import graphviz
import logging

from logfix import get_format_spec
from pprint import pprint

log = logging.getLogger('test')
world = 'world'

identifiers = dict()


def get_identifier(root: str) -> str:
    if root in identifiers:
        n = identifiers[root]
    else:
        n = 1
    identifiers[root] = n + 1
    return f'{root}_{n}'


def get_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Attribute):
        return get_name(node.value) + '.' + node.attr
    if isinstance(node, ast.Mod):
        return '%'
    if isinstance(node, ast.Add):
        return '+'
    if isinstance(node, ast.Sub):
        return '-'
    return f'{type(node)} {node}'

def make_label(type: str, value: str) -> str:
    value = value.replace('{', '\\{').replace('}', '\\}')
    return '{' + type + '|' + value + '}'


def create_node(G, label: str) -> str:
    id = get_identifier('node')
    G.node(id, label=label)
    return id


def render_binop(G, node: ast.BinOp) -> str:
    binop = create_node(G, make_label('ast.BinOp', get_name(node.op)))
    lhs = render_arg(G, node.left)
    G.edge(binop, lhs)
    if isinstance(node.right, ast.Name) or isinstance(node.right, ast.Constant) or isinstance(node.right, ast.Attribute) or isinstance(node.right, ast.Call):
        rhs = render_arg(G, node.right)
        G.edge(binop, rhs)
    elif isinstance(node.right, ast.Tuple):
        tuple = create_node(G, 'ast.Tuple')
        G.edge(binop, tuple)
        for arg in node.right.elts:
            tuple_arg = render_arg(G, arg)
            G.edge(tuple, tuple_arg)
    return binop


def create_node_for(G, node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return create_node(G, label=make_label('ast.Name', node.id))
    if isinstance(node, ast.Constant):
        return create_node(G, label=make_label('ast.Constant', node.value))
    if isinstance(node, ast.Attribute):
        name = get_name(node.value) + '.' + node.attr
        return create_node(G, make_label('ast.Name', name))
    if isinstance(node, ast.BinOp):
        return render_binop(G, node)
    if isinstance(node, ast.Mod):
        return create_node(G, make_label('ast.BinOp', '%'))
    if isinstance(node, ast.Add):
        return create_node(G, make_label('ast.BinOp', '+'))
    if isinstance(node, ast.Sub):
        return create_node(G, make_label('ast.BinOp', '-'))


def render_fstring(G, node: ast.JoinedStr):
    fstring = create_node(G, 'ast.JoinedStr')
    for part in node.values:
        if isinstance(part, ast.Constant):
            const = create_node(G, make_label('ast.Constant', "'" + part.value + "'"))
            G.edge(fstring, const)
        elif isinstance(part, ast.FormattedValue):
            fv = create_node(G, 'ast.FormattedValue')
            G.edge(fstring, fv)
            value = create_node_for(G, part.value)
            print(f"Created node {value}")
            G.edge(fv, value)
            if part.format_spec is None:
                fspec = 'None'
            else:
                if part.format_spec is None:
                    fspec = 'None'
                else:
                    fspec = part.format_spec.values[0].value
            spec = create_node(G, make_label('format_spec', fspec))
            G.edge(fv, spec)
    return fstring


def render_arg(G, node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        name = create_node(G, make_label('ast.Constant', node.value))
    elif isinstance(node, ast.Name):
        name = create_node(G, make_label('ast.Name', node.id))
    elif isinstance(node, ast.Attribute):
        name = get_name(node.attr)
        G.node(name, label=name)
    elif isinstance(node, ast.BinOp):
        name = render_binop(G, node)
    elif isinstance(node, ast.Call):
        name = render_call(G, node)
    elif isinstance(node, ast.JoinedStr):
        name = render_fstring(G, node)
    else:
        raise Exception(f'Unhandled arg type {type(node)}')
    return name


def render_call(G, node: ast.Call) -> str:
    call = create_node(G, 'ast.Call')

    fname = get_name(node.func)
    func = create_node(G, make_label('func', fname))

    args = create_node(G, 'args: list')
    G.edge(call, func)
    G.edge(call, args)
    for arg in node.args:
        arg_node = render_arg(G, arg)
        G.edge(args, arg_node)
    return call



def run(statement, filename=None):
    tree = ast.parse(statement, 'test.py')
    call = tree.body[0].value
    G = graphviz.Digraph('AST', filename=filename, graph_attr=dict(label=statement, labelloc="t"), node_attr=dict(shape="record"))
    render_call(G, call)
    G.view()
    if filename is not None:
        print(f'Saving {filename}')
        G.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser('astview.py', description='Generate a Graphviz (DOT) view of a simple AST', epilog='Copyright 2023 The Galaxy Project (https://galaxyproject.org')
    parser.add_argument('-s', '--statement', help='a Python logging statement')
    parser.add_argument('-f', '--filename', help='write the AST to a .dot file.', nargs='?')

    args = parser.parse_args()
    print(f"Statement: {args.statement}")
    run(args.statement, args.filename)
    sys.exit()