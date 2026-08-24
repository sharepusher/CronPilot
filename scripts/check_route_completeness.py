#!/usr/bin/env python3
"""
Check that every Flask view function with @require_permission also has a @blueprint.route decorator.

Usage:
    python scripts/check_route_completeness.py --check app/rbac/views.py
    python scripts/check_route_completeness.py app/rbac/views.py app/main/views.py
"""
import ast
import sys


def check_file(path: str) -> list:
    """Return list of (lineno, funcname) for view functions missing @route decorator."""
    with open(path, encoding='utf-8') as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [(0, f'SYNTAX ERROR: {e}')]

    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        has_route = False
        has_permission = False
        for deco in node.decorator_list:
            # @blueprint.route(...)
            if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                if deco.func.attr == 'route':
                    has_route = True
            # @require_permission(...)
            if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Name):
                if deco.func.id == 'require_permission':
                    has_permission = True
        if has_permission and not has_route:
            issues.append((node.lineno, node.name))
    return issues


def main():
    check_mode = '--check' in sys.argv
    paths = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not paths:
        print('Usage: check_route_completeness.py [--check] <file1.py> [file2.py ...]')
        sys.exit(1)

    total_issues = []
    for path in paths:
        issues = check_file(path)
        for lineno, funcname in issues:
            total_issues.append((path, lineno, funcname))
            print(f'ERROR  {path}:{lineno}  {funcname}() has @require_permission but no @route decorator')

    if not total_issues:
        print(f'OK  All route functions in {", ".join(paths)} have @route decorators.')
        sys.exit(0)
    else:
        print(f'\n{len(total_issues)} issue(s) found.')
        if check_mode:
            sys.exit(1)


if __name__ == '__main__':
    main()
