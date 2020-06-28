import tabulate

import capa.rules
import capa.render.utils as rutils


def render_statement(ostream, statement, indent=0):
    ostream.write('  ' * indent)
    if statement['type'] in ('and', 'or', 'optional'):
        ostream.write(statement['type'])
        ostream.writeln(':')
    elif statement['type'] == 'not':
        # we won't have successful results for the children of a not
        # so display a placeholder `...`
        ostream.writeln('not: ...')
    elif statement['type'] == 'some':
        ostream.write(statement['count'] + ' or more')
        ostream.writeln(':')
    elif statement['type'] == 'range':
        # `range` is a weird node, its almost a hybrid of statement+feature.
        # it is a specific feature repeated multiple times.
        # there's no additional logic in the feature part, just the existence of a feature.
        # so, we have to inline some of the feature rendering here.

        child = statement['child']
        if child['type'] in ('string', 'bytes', 'api', 'mnemonic', 'basic block', 'export', 'import', 'section', 'match'):
            feature = '%s(%s)' % (child['type'], rutils.bold2(child[child['type']]))
        elif child['type'] in ('number', 'offset'):
            feature = '%s(%s)' % (child['type'], rutils.bold2(rutils.hex(child[child['type']])))
        elif child['type'] == 'characteristic':
            feature = 'characteristic(%s)' % (rutils.bold2(child['characteristic'][0]))
        else:
            raise RuntimeError('unexpected feature type: ' + str(child))

        ostream.write('count(%s): ' % feature)

        if statement['max'] == statement['min']:
            ostream.writeln('%d' % (statement['min']))
        elif statement['min'] == 0:
            ostream.writeln('%d or fewer' % (statement['max']))
        elif statement['max'] == (1 << 64 - 1):
            ostream.writeln('%d or more' % (statement['min']))
        else:
            ostream.writeln('between %d and %d' % (statement['min'], statement['max']))
    elif statement['type'] == 'subscope':
        ostream.write(statement['subscope'])
        ostream.writeln(':')
    elif statement['type'] == 'regex':
        # regex is a `Statement` not a `Feature`
        # this is because it doesn't get extracted, but applies to all strings in scope.
        # so we have to handle it here
        ostream.writeln('string: %s' % (statement['match']))
    else:
        raise RuntimeError("unexpected match statement type: " + str(statement))


def render_feature(ostream, match, feature, indent=0):
    ostream.write('  ' * indent)

    if feature['type'] in ('string', 'api', 'mnemonic', 'basic block', 'export', 'import', 'section', 'match'):
        ostream.write(feature['type'])
        ostream.write(': ')
        ostream.write(rutils.bold2(feature[feature['type']]))
    elif feature['type'] in ('number', 'offset'):
        ostream.write(feature['type'])
        ostream.write(': ')
        ostream.write(rutils.bold2(rutils.hex(feature[feature['type']])))
    elif feature['type'] == 'bytes':
        ostream.write('bytes: ')
        # bytes is the uppercase, hex-encoded string.
        # it should always be an even number of characters (its hex).
        bytes = feature['bytes']
        for i in range(len(bytes) // 2):
            ostream.write(rutils.bold2(bytes[i:i + 2]))
            ostream.write(' ')
    elif feature['type'] == 'characteristic':
        ostream.write('characteristic(%s)' % (rutils.bold2(feature['characteristic'][0])))
    # note that regex is found in `render_statement`
    else:
        raise RuntimeError('unexpected feature type: ' + str(feature))

    locations = list(sorted(match['locations']))
    if len(locations) == 1:
        ostream.write(' @ ')
        ostream.write(rutils.hex(locations[0]))
    elif len(locations) > 1:
        ostream.write(' @ ')
        if len(locations) > 4:
            # don't display too many locations, because it becomes very noisy.
            # probably only the first handful of locations will be useful for inspection.
            ostream.write(', '.join(map(rutils.hex, locations[0:4])))
            ostream.write(', and %d more...' % (len(locations) - 4))
        else:
            ostream.write(', '.join(map(rutils.hex, locations)))

    ostream.write('\n')


def render_node(ostream, match, node, indent=0):
    if node['type'] == 'statement':
        render_statement(ostream, node['statement'], indent=indent)
    elif node['type'] == 'feature':
        render_feature(ostream, match, node['feature'], indent=indent)
    else:
        raise RuntimeError('unexpected node type: ' + str(node))


def render_match(ostream, match, indent=0):
    if not match['success']:
        return

    if match['node'].get('statement', {}).get('type') == 'optional' and not any(map(lambda m: m['success'], match['children'])):
        return

    render_node(ostream, match, match['node'], indent=indent)

    for child in match['children']:
        render_match(ostream, child, indent=indent + 1)


def render_vverbose(doc):
    ostream = rutils.StringIO()

    for rule in rutils.capability_rules(doc):
        ostream.writeln(rutils.bold(rule['meta']['name']))

        rows = []
        for key in capa.rules.META_KEYS:
            if key == 'name' or key not in rule['meta']:
                continue

            v = rule['meta'][key]
            if isinstance(v, list) and len(v) == 1:
                v = v[0]
            elif isinstance(v, list) and len(v) > 1:
                v = ', '.join(v)
            rows.append((key, v))

        ostream.writeln(tabulate.tabulate(rows, tablefmt='plain'))

        if rule['meta']['scope'] == capa.rules.FILE_SCOPE:
            render_match(ostream, match, indent=0)
        else:
            for location, match in doc[rule['meta']['name']]['matches'].items():
                ostream.write(rule['meta']['scope'])
                ostream.write(' @ ')
                ostream.writeln(rutils.hex(location))
                render_match(ostream, match, indent=1)

        ostream.write('\n')

    return ostream.getvalue()
