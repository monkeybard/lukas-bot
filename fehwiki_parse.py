import urllib.request, urllib.parse, json, io, operator, unidecode
from socket import timeout
from bs4 import BeautifulSoup as BSoup
from feh_alias import *
from feh_personal import *

feh_source = "https://feheroes.gamepedia.com/%s"
INVALID_HERO = 'no'
GAUNTLET_URL = "https://support.fire-emblem-heroes.com/voting_gauntlet/current"

weapon_colours = {'Red':0xCC2844, 'Blue':0x2A63E6, 'Green':0x139F13, 'Colourless':0x54676E, 'Null':0x222222}
passive_colours = [0xcd914c, 0xa8b0b0, 0xd8b956, 0xfff208]
valid_categories = ['Heroes', 'Passives', 'Weapons', 'Specials', 'Assists', 'Disambiguation pages', 'Enemy units']


def shorten_hero_name(name):
    main_name, epithet = name.split(':')
    return main_name + ':' + ''.join(list(filter(lambda c: c.isalpha(), w))[0] for w in epithet.strip().split(' ')
                                     if any([c.isalpha() for c in w]))

def parse_inherit_restriction(inherit_r):
    try:
        inherit_r = inherit_r.get_text().strip() + " " + \
                    ((', '.join([a["title"] for a in inherit_r.find_all("a")])).strip() if inherit_r.find(
                        "a") is not None else '')
    except KeyError:
        # maybe a html error
        try:
            inherit_r = BSoup(inherit_r.get_text().strip(), "lxml")
            inherit_r = inherit_r.get_text().strip() + " " + \
                        ((', '.join([a["title"] for a in inherit_r.find_all("a")])).strip() if inherit_r.find(
                            "a") is not None else '')
        except KeyError:
            inherit_r = "*Inherit restrictions could not be parsed at this time. Please refer to the source page.*"
    return inherit_r

def get_data(arg, timeout_dur=5):
    categories, html = get_page_html(arg, timeout_dur)
    if html is None:
        return None, None, None
    for br in html.find_all('br'):
        br.replace_with('\n')
    data = {'Embed Info': {'Title': arg, 'Icon': None}}
    other_referenced_pages = []
    if 'Heroes' in categories or 'Enemy units' in categories:
        first_table = html.find('table', attrs={'class':'wikitable'})
        if first_table.text.strip().startswith('You may') and first_table.td is not None:
            alts = [a.text.strip() for a in first_table.td.find_all('div', attrs={"class":"tooltiptext"}) if a is not None and a.text]
            data['Message'] = '**You may be looking for:** '+ ', '.join(alts)
            other_referenced_pages.extend(set(alts))
        elif any(['This page is about' in content.text for content in html.find_all('i')]):
            alts = [content.text for content in html.find_all('i') if 'This page is about' in content.text][0]
            data['Message'] = '*' + alts.strip() + '*'
        stats = get_hero_infobox(html)
        if 'Legendary Heroes' in categories:
            data['2Element'] = "{} ({})".format(stats['effect'].strip(), stats['ally boost']), False
        base_stats_table, max_stats_table = get_heroes_stats_tables(html)
        colour = weapon_colours['Colourless']
        if any(i in stats['weapon type'] for i in ['Red', 'Sword']):
            colour = weapon_colours['Red']
        if any(i in stats['weapon type'] for i in ['Blue', 'Lance']):
            colour = weapon_colours['Blue']
        if any(i in stats['weapon type'] for i in ['Green', 'Axe']):
            colour = weapon_colours['Green']
        data['Embed Info']['Colour'] = colour
        data['Embed Info']['URL'] = feh_source % (urllib.parse.quote(arg))
        icon = get_icon(''.join(filter(lambda x: x.isalpha() or x in [' ', '-'], arg)), suffix="_Face_FC")
        if not icon is None:
            data['Embed Info']['Icon'] = icon
        if 'rarities' in stats:
            rarity = '-'.join(a+'★' for a in stats['rarities'] if a.isdigit())
            data['0Rarities'] = (rarity if rarity else 'N/A'), True
        bst = get_bst(max_stats_table)
        if bst is not None:
            data['1BST'] = bst, True
        data['2Weapon Type'] = stats['weapon type'], True
        data['3Move Type'] = stats['move type'], True
        if base_stats_table:
            data['4Base Stats'] = base_stats_table, False
        if max_stats_table:
            data['5Max Level Stats'] = max_stats_table, False
        skill_tables = html.find_all("table", attrs={"class":"skills-table"})
        skills = ''
        for table in skill_tables:
            headings = [a.get_text().strip() for a in table.find_all("th")]
            if 'Might' in headings:
                # weapons
                skills += '**Weapons:** '
            elif 'Range' in headings:
                # assists
                skills += '**Assists:** '
            elif 'Cooldown' in headings:
                # specials
                skills += '**Specials:** '
            last_learned = None
            in_passives = False
            for row in table.find_all("tr")[1:]:
                if row.find("td") is not None:
                    slot = row.find("td", attrs={"rowspan":True}) # only passives have a rowspan data column
                    if not slot is None:
                        in_passives = True
                        skills = skills.rstrip(', ')
                        if not last_learned is None:
                            skills += last_learned
                        skills += '\n**' + slot.get_text() + ':** '
                    skills += row.find_all("td")[1 if in_passives else 0].get_text().strip()
                    other_referenced_pages.append(row.find_all("td")[1 if in_passives else 0].a['href'].lstrip('/').replace('_',' '))
                    last_learned = ' (%s★)' % row.find_all("td")[-2 if not slot is None else -1].get_text().strip() # get learned levels
                    skills += ', '
            if skills:
                skills = skills.rstrip(', ') + last_learned + '\n'
        if skills:
            data['6Learnable Skills'] = skills, False

    elif 'Weapons' in categories:
        colour = weapon_colours['Null'] # for dragonstones and bows, which are any colour
        if any(i in ['Swords', 'Red Tomes'] for i in categories):
            colour = weapon_colours['Red']
        elif any(i in ['Lances', 'Blue Tomes'] for i in categories):
            colour = weapon_colours['Blue']
        elif any(i in ['Axes', 'Green Tomes'] for i in categories):
            colour = weapon_colours['Green']
        elif any(i in ['Staves', 'Daggers'] for i in categories):
            colour = weapon_colours['Colourless']
        data['Embed Info']['Colour'] = colour
        data['Embed Info']['URL'] = feh_source % (urllib.parse.quote(arg))
        icon = get_icon(arg, "Weapon_")
        if not icon is None:
            data['Embed Info']['Icon'] = icon
        stats = get_infobox(html)
        if 'Might' in stats and stats['Might']:
            data['0Might'] = stats['Might'], True
        if 'Range' in stats and stats['Range']:
            data['1Range'] = stats['Range'], True
        if 'SP' in stats and stats['SP']:
            data['2SP Cost'] = stats['SP'], False
        if 'Exclusive?' in stats and stats['Exclusive?']:
            data['3Exclusive?'] = stats['Exclusive?'], True
        if 'Description' in stats:
            data['5Description'] = stats['Description'].replace('  ', ' ').strip(), False
        ps = html.find_all('p')
        if any(['can be evolved from' in p.text for p in ps]):
            data['6Evolves from'] = ps[ps.index([p for p in ps if 'can be evolved from' in p.text][0])].a.text.strip(), False
        learners_table = html.find("table", attrs={"class":"sortable"})
        if learners_table:
            learners = ', '.join(map(shorten_hero_name, [a.find("td").find_all("a")[1].get_text().replace('\n', ' ') for a in learners_table.find_all("tr")[1:]]))
            if learners:
                data['6Heroes with ' + arg] = learners, False
        refinery_tables = html.find_all("table", attrs={"class":"wikitable default"})
        for refinery_table in refinery_tables:
            if not refinery_table.text.strip().startswith('Language'):
                refinery_table = extract_table(refinery_table, True)
                if refinery_table:
                    if 'Image' in refinery_table[0]:
                        cost = refinery_table[0]['Cost'].split('|')
                        if any(cost):
                            cost_materials = cost[1:]
                            cost = cost[0].split('\n')
                            cost[1] = cost[1].strip().lstrip('SP') + ' ' + cost_materials[0].strip() + 's'
                            cost[2] = cost[2].strip() + ' ' + cost_materials[1].strip() + 's'
                            cost = ', '.join(cost)
                        else:
                            cost = 'Unknown'
                        data['Evolution'] = refinery_table[0]['Name'].split('|')[0], False
                        data['Evolution Cost'] = cost
                    elif 'Type' in refinery_table[0]:
                        data['Refine'] = []
                        first_r = refinery_table[0]['Type'].split('|')[1]
                        if not first_r.startswith('Attack') and not first_r.startswith('Wrathful'):
                            icon = get_icon(first_r)
                            if icon:
                                data['Refine Icon'] = icon
                        for r in refinery_table:
                            t = r['Type'].split('|')[1].rstrip(' W')
                            s = r['Stats'].split('|')[0]
                            e = r['Description'].split('|')[0].replace('  ', ' ')
                            cost = r['Cost'].split('|')
                            if any(cost):
                                cost_materials = cost[1:]
                                cost = cost[0].split(', ')
                                cost[1] = cost[1].strip() + ' ' + cost_materials[0].strip() + 's'
                                cost[2] = cost[2].strip() + ' ' + cost_materials[1].strip() + 's'
                                cost = ', '.join(cost)
                            else:
                                cost = 'Unknown'
                            data['Refine'].append({'Type':t if t else 'Unknown', 'Stats':s if s else 'No Stat Changes',
                                                   'Effect':e if e else 'No Effect'})
                            data['Refinery Cost'] = cost
    elif 'Passives' in categories:
        stats_table = html.find("table", attrs={"class": "skills-table"})
        stat_rows = stats_table.find_all("tr")[1:]
        data = {'Embed Info': {'Title': arg}, 'Data': []}
        inherit_r = None
        if stat_rows[-1].text.strip().startswith("Cannot use:") or \
                stat_rows[-1].text.strip().startswith("No restrictions.") or \
                stat_rows[-1].text.strip().startswith("This skill can only") or \
                stat_rows[-1].text.strip().startswith("Unknown"):
            inherit_r = stat_rows.pop()
            inherit_r = parse_inherit_restriction(inherit_r)
        curr_row = 1 if len(stat_rows) == 2 else 0
        for row in stat_rows:
            temp_data = {'Embed Info': {'Title': arg, 'Icon': None}}
            stats = [a.get_text().strip() for a in row.find_all("td")]
            stats = [a if a else 'N/A' for a in stats]
            if stats[0] != 'N/A' and len(stats) > 5:
                slot = stats.pop(0)
            temp_data['Embed Info']['Colour'] = 0xe8e1c9 if len(stat_rows) == 1\
                                        else passive_colours[curr_row]
            curr_row += 1
            skill_name = stats[1]
            learners = None
            if 'Seal Exclusive Skills' not in categories:
                learners_table = html.find_all("table", attrs={"class": "sortable"})
                if learners_table and len(learners_table) > 0:
                    learners_table = learners_table[-1]
                    if learners_table != stats_table:
                        learners = get_learners(learners_table, skill_name)
            temp_data['Embed Info']['Title'] = skill_name
            temp_data['Embed Info']['URL'] = feh_source % (urllib.parse.quote(arg))
            icon = get_icon(stats[1])
            if not icon is None:
                temp_data['Embed Info']['Icon'] = icon
            temp_data['0Slot'] = (slot + ('/S' if 'Sacred Seals' in categories and slot != 'S' else '')), True
            temp_data['1SP Cost'] = stats[2][4 if stats[2].startswith('30px') else 0:], True
            temp_data['2Effect'] = stats[4].replace('\n', ' '), False
            if len(stats) > 5:
                inherit_r = parse_inherit_restriction(row.find_all("td")[-1])
                if not inherit_r.startswith('No restrictions'):
                    inherit_r = "Cannot use: " + inherit_r
            temp_data['3Inherit Restrictions'] = inherit_r, True
            if learners:
                if 'Sacred Seals' in categories:
                    learners = 'Available as Sacred Seal\n' + learners
                temp_data['4Heroes with ' + arg] = learners, False
            data['Data'].append(temp_data)
    elif 'Specials' in categories or 'Assists' in categories:
        stats_table = html.find("table", attrs={"class": "skills-table"})
        data_row = stats_table.find_all("tr")[1]
        stats = [a.get_text().strip() for a in data_row.find_all("td")]
        stats = [a if a else 'N/A' for a in stats]
        if 'Specials' in categories:
            data['Embed Info']['Colour'] = 0xf499fe
        elif 'Assists' in categories:
            data['Embed Info']['Colour'] = 0x1fe2c3

        if 'Staff Assists' in categories:
            icon = get_icon(arg, "Weapon_")
            if not icon is None:
                data['Embed Info']['Icon'] = icon

        data['Embed Info']['Title'] = arg
        data['Embed Info']['URL'] = feh_source % (urllib.parse.quote(arg))
        if 'Specials' in categories:
            data['0Cooldown'] = stats[1], True
        elif 'Assists' in categories:
            data['0Range'] = stats[1], True
        data['1SP Cost'] = stats[3], True
        data['2Effect'] = stats[2], False
        data['3Prequirement'] = stats[-1].replace('\n', ', '), False
        inherit_r = stats_table.find_all("tr")[-1]
        inherit_r = parse_inherit_restriction(inherit_r)

        data['4Inherit Restrictions'] = inherit_r, True
        if 'Specials' in categories:
            if 'Area of Effect Specials' in categories:
                range = ''
                for row in html.find_all('table', attrs={"class":'wikitable'})[1].find_all('tr'):
                    for d in row.find_all('td'):
                        if d.img:
                            if 'Special' in d.img['alt']:
                                range += 'X'
                            else:
                                range += 'O'
                        else:
                            range += ' '
                    range += '\n'
                data['3Area of Effect'] = '```' + range + '```', False
        learners = get_learners(html.find_all("table", attrs={"class":"sortable"})[-1], stats[0])
        if learners:
            data['5Heroes with ' + arg] = learners, False
    else:
        data['Embed Info']['URL'] = feh_source % (urllib.parse.quote(arg))
        data['Embed Info']['Colour'] = weapon_colours['Null']

        if categories:
            data['1Categories'] = ', '.join(categories), False

        if 'Disambiguation pages' in categories:
            valid_ambiguous_people = ['Robin', 'Corrin', 'Tiki', 'Morgan', 'Grima', 'Falchion', 'Kana', 'Byleth']
            options = [option.a['title'].strip() for option in html.find_all('li')]
            if arg in valid_ambiguous_people:
                data['1Could refer to:'] = '\n'.join(options), False
            else:
                # connect to the first one
                return get_data(options[0], timeout_dur=timeout_dur)
        elif 'Persons' in categories:
                first_hero_link = [a for a in html.find_all('a') if "title" in a.attrs and arg in a.text]
                if first_hero_link:
                    new_categories, new_data, other_pages = get_data(first_hero_link[0]["title"].strip(), timeout_dur=timeout_dur)
                    if new_categories is None:
                        return ['Persons'], data, other_referenced_pages
                    else:
                        return new_categories, new_data, other_pages
        # check if soft redirect
        elif 'redirect' in html.text.strip().lower():
            return get_data(html.a.text.strip(), timeout_dur=timeout_dur)
        elif arg.startswith('Category:'):
            page = get_page(
                'http://feheroes.gamepedia.com/api.php?action=query&list=categorymembers&cmtitle={}&cmlimit=500&cmtype=page&cmcontinue'.format(
                    urllib.parse.quote(arg)))
            members = page['query']['categorymembers']
            while 'continue' in page:
                page = get_page(
                    'http://feheroes.gamepedia.com/api.php?action=query&list=categorymembers&cmtitle={}&cmlimit=500&cmtype=page&cmcontinue={}'.format(
                        urllib.parse.quote(arg), page['continue']['cmcontinue']))
                members.extend(page['query']['categorymembers'])
            data['1Total Pages'] = len(members), False
            # num_pages = 0
            # items_per_page = 25
            # while num_pages * items_per_page < len(members) and num_pages < 3:
            #     start = num_pages * items_per_page
            #     end = start + items_per_page
            #     data['2Pages {}-{}'.format(start+1, min(end, len(members)))] = '\n'.join([m['title'] for m in members[start:end]]), True
            #     num_pages += 1
            data['2First 20 Pages'] = '\n'.join([m['title'] for m in members[:20]]), True
        else:
            for b in html.find_all('b'):
                b.replace_with('**{}**'.format(b.text))
            for i in html.find_all('i'):
                i.replace_with('*{}*'.format(i.text))

            if 'A new challenger approaches!' in html.text:
                # destroy stub text
                html.tbody.decompose()
                html.tbody.decompose()

            data['2Summary'] = html.p.text.strip()[:1000], False

    return categories, data, other_referenced_pages


def get_page(url, prop='', timeout_dur=5):
    query_url = url+('&prop='+prop if prop else '')+'&format=json'
    print(query_url)
    request = urllib.request.Request(query_url, headers={'User-Agent': 'Mozilla/5.0'})
    if timeout:
        response = urllib.request.urlopen(request, timeout=timeout_dur)
    else:
        response = urllib.request.urlopen(request)
    print('Loading JSON...')
    info = json.load(response)
    if 'error' in info:
        return None
    return info


def find_name(arg, cache, ctx=None):
    # check if the arg is son or waifu and sees if the user has one
    sender = ctx.message.author if ctx else None
    if sender:
        if arg.lower() in ['son', 'my son']:
            if str(sender) in cache.sons:
                cache.set_fam('son', str(sender.id), cache.sons[str(sender)])
                del cache.sons[str(sender)]
            if str(sender.id) in cache.sons:
                return cache.sons[str(sender.id)]
        elif arg.lower() in ['waifu', 'my waifu']:
            if str(sender) in cache.waifus:
                cache.set_fam('waifu', str(sender.id), cache.waifus[str(sender)])
                del cache.waifus[str(sender)]
            if str(sender.id) in cache.waifus:
                return cache.waifus[str(sender.id)]

    if arg.lower() in ['son', 'my son', 'waifu', 'my waifu']:
        return INVALID_HERO

    # check cached aliases
    result = cache.resolve_alias(arg)
    if result:
        return result

    # basic quick stat aliasing without needing manual input
    # enough to be vaguely useful without messing with some other skills
    arg = arg.lower().replace('hp+', 'hp plus').replace('atk+', 'attack plus').replace('spd+', 'speed plus').\
        replace('def+', 'defense plus').replace('res+', 'resistance plus').replace('hp+', 'hp plus').\
        replace('attack+', 'attack plus').replace('speed+', 'speed plus').replace('defense+', 'defense plus').\
        replace('resistance+', 'resistance plus').replace(' +', ' plus')

    # resolve webpage
    redirect = feh_source % "api.php?action=opensearch&search=%s&redirects=resolve" % (urllib.parse.quote(arg))
    info = get_page(redirect)
    if not info[1] or not info[1][0]:
        return INVALID_HERO
    else:
        return sorted(sorted(info[1]), key=lambda i: len(i))[0]
    return arg


def get_heroes_list():
    # get table from html
    categories, html = get_page_html('Level 40 stats table')
    table = html.find_all('table')[-1]
    heroes_list = []
    # add all the rows that fit the format to current list
    for row in table.find_all('tr'):
        try:
            heroes_list.append(list_row_to_dict(row))
        except KeyError:
            pass
    # take out all the ones with incomplete data
    heroes_list = list(filter(lambda h:h['BST'] != 0, heroes_list))
    heroes_list = {r['Name']: r for r in heroes_list}
    return heroes_list


def list_row_to_dict(row):
    data = row.find_all('td')
    colour, weapon = row['data-weapon-type'].split()
    hero = {
        'Name':data[1].text,
        'Colour':colour,
        'Weapon':weapon,
        'Movement':row['data-move-type'],
        'HP':int(data[4].text) if data[4].text.isdigit() else 0, 'ATK':int(data[5].text) if data[5].text.isdigit() else 0,
        'SPD':int(data[6].text) if data[6].text.isdigit() else 0, 'DEF':int(data[7].text) if data[7].text.isdigit() else 0,
        'RES':int(data[8].text) if data[8].text.isdigit() else 0, 'BST':int(data[9].text) if data[9].text.isdigit() else 0
    }
    return hero


def get_icon(arg, prefix="", suffix=""):
    url = feh_source %\
          "api.php?action=query&titles=File:%s%s%s.png" %\
          (prefix, urllib.parse.quote(unidecode.unidecode(arg.replace('+', '_Plus' + '_' if not prefix == "Weapon_" else '_Plus'))), suffix)
    info = get_page(url, 'imageinfo&iiprop=url')
    if '-1' in info['query']['pages']:
        if "'" in arg:
            return get_icon(arg.replace("'",""), prefix, suffix)
        return None
    else:
        icon = info['query']['pages'][next(iter(info['query']['pages']))]['imageinfo'][0]['url']
        return icon


def get_page_html(arg, timeout_dur=5):
    url = feh_source % "api.php?action=parse&page=%s" % (urllib.parse.quote(arg))
    info = get_page(url, 'text|categories', timeout_dur)
    if info:
        categories = [' '.join(k['*'].split('_')) for k in info['parse']['categories']]
        soup = BSoup(info['parse']['text']['*'], "lxml")
        return categories, soup
    else:
        return None, None


def get_infobox(html):
    table = html.find("div", attrs={"class": "hero-infobox"}).find("table")
    return {a.find("th").get_text().replace('  ', ' ').strip() if not a.find("th") is None else None: a.find(
        "td").get_text().strip() if not a.find("td") is None else None for a in table.find_all("tr") if a.find("audio") is None}


def get_hero_infobox(html):
    table = html.find(attrs={"class": "hero-infobox"}).find_all("tr")#[-1].find("div").find_all("div", attrs={"style": "width:100%"})
    table = {(r.th.get_text().strip().lower() if r.th else None) : (r.td.get_text().replace('  ',' ').strip() if r.td else None) for r in table}
    # table = [div.find_all("div") for div in table]
    # table = {d.th.get_text().replace('  ',' ').strip().lower(): d.td.get_text().replace('  ',' ').strip() for d in table}
    return table


def get_heroes_stats_tables(html):
    tables = html.find_all("table", attrs={"class":"wikitable"})
    tables = [table for table in tables if 'Rarity' in table.text]
    if len(tables) < 2:
        return [None, None]
    return [extract_table(a, cap_keys=True) for a in tables[0:2]]


def extract_table(table_html, get_image_url=False, cap_keys=False):
    table = []
    headings = [a.get_text().strip() for a in table_html.find_all("th")]
    for learner in table_html.find_all("tr"):
        if len(learner.find_all("td")) == 0:
            continue
        data = []
        for a in learner.find_all("td"):
            d = a.get_text().strip()
            if get_image_url and a.a:
                d += '|' + '|'.join([b['href'].strip().lstrip('/').\
                                    replace('File:','').replace('.png','').replace('_', ' ')
                                     for b in a.find_all('a')]) + '|'
            data.append(d)
        table.append({(headings[a].upper() if cap_keys else headings[a]): data[a] for a in range(0, len(headings))})
    return table


def format_stats_table(table):
    if len(table) == 0:
        return None
    ivs = {'HP':'', 'ATK':'', 'SPD':'', 'DEF':'', 'RES':'', 'TOTAL':''}
    keys = ['RARITY', 'HP', 'ATK', 'SPD', 'DEF', 'RES', 'TOTAL']
    rows = ''
    for set in table:
        rows += '\n'
        for key in keys:
            if key == keys[0]:
                rows += '|' + set[key] + '★|'
                continue
            if key == keys[-1]:
                continue
            stats = set[key].split('/')
            neutral = stats[0]
            format = '%4s'
            if len(stats) == 3:
                neutral = stats[1]
                if neutral.isdigit() and len(list(filter(lambda x:x.isdigit(), stats))) == 3:
                    if int(stats[2]) - int(stats[1]) == 4:
                        ivs[key] = '+'
                    if int(stats[1]) - int(stats[0]) == 4:
                        if ivs[key] == '+':
                            ivs[key] = '±'
                        else:
                            ivs[key] = '-'
            rows += format % neutral + '|'
    header = '```|' + '|'.join([format % (ivs[key] + key) if key != keys[0] else ' ★' for key in keys][:-1]) + '|'
    rows += '```'
    ret = header + rows
    if '+' in list(ivs.values()) or '-' in list(ivs.values()):
        ret += "_Neutral stats.\n+4 boons are indicated by +, -4 banes are indicated by -._"
    return ret


def get_bst(stats_table):
    if not stats_table or len(stats_table) == 0 or 'TOTAL' not in stats_table[-1]:
        return None
    return stats_table[-1]['TOTAL']


def get_learners(learners_table, skill_name):
    learners = {i+1:[] for i in range(5)}
    # l_data is one row in a 2D array representing the learners table
    for l_data in [a.find_all("td") for a in learners_table.find_all("tr")]:
        if l_data:
            # append a name to the appropriate level
            for i in range(len(l_data)):
                text = l_data[i].get_text()
                if skill_name in text and text[-1].isdigit():
                    learned_level = int(text[-1])
                    learners[learned_level].append(shorten_hero_name(l_data[0].find_all("a")[1].get_text().replace('\n', ' ')))
                    break
    learners = '\n'.join(['%d★: %s' % (level, ', '.join(learners[level])) for level in learners if len(learners[level]) != 0])
    return learners

def get_gauntlet_scores():
        newurl = urllib.request.urlopen(GAUNTLET_URL).geturl()
        toopen = urllib.request.Request(newurl, headers={'Accept-Language':'en-GB'})
        html = BSoup(urllib.request.urlopen(toopen).read(), "lxml")
        round = html.find_all('ul')[2]
        scores = [[m.find('div', attrs={'class':'tournaments-art-left'}), m.find('div', attrs={'class':'tournaments-art-right'})] for m in round.find_all('li')]
        scores = [[{'Name':s[0].p.text, 'Score':s[0].find_all('p')[-1].text, 'Status':'Same' if 'normal' in s[0]['class'][-1] else 'Weak'},
                    {'Name':s[1].p.text, 'Score':s[1].find_all('p')[-1].text, 'Status':'Same' if 'normal' in s[1]['class'][-1] else 'Weak'}] for s in scores]
        for s in scores:
            if s[0]['Status'] == 'Weak':
                s[1]['Status'] = 'Strong'
            elif s[1]['Status'] == 'Weak':
                s[0]['Status'] = 'Strong'
        return scores


def standardize(d, k):
    l = d[k]
    valid_filters = ['Red', 'Blue', 'Green', 'Colorless', 'Sword', 'Lance', 'Axe', 'Bow', 'Staff', 'Breath', 'Tome', 'Dagger', 'Infantry', 'Cavalry', 'Armored', 'Flying']
    valid_sorts = ['HP', 'ATK', 'SPD', 'DEF', 'RES', 'BST', 'Name', 'Colour', 'Weapon', 'Movement']
    for i in range(len(l)):
        l[i] = l[i].title().rstrip('s') if (l[i].title() not in ['Colourless', 'Colorless'] and not l[i].lower().endswith('res')) else l[i].title()
        if l[i] in ['R', 'Re']:
            l[i] = 'Red'
        if l[i] in ['B', 'Bl']:
            l[i] = 'Blue'
        if l[i] in ['G', 'Gr']:
            l[i] = 'Green'
        if l[i] in ['C', 'Colourless', 'Colorless', 'Ne', 'N']:
            l[i] = 'Colorless'
        if l[i] == 'Sw':
            l[i] = 'Sword'
        if l[i] == 'La':
            l[i] = 'Lance'
        if l[i] == 'Ax':
            l[i] = 'Axe'
        if l[i] == 'Bo':
            l[i] = 'Bow'
        if l[i] in ['St', 'Stave']:
            l[i] = 'Staff'
        if l[i] in ['Br', 'Dragon']:
            l[i] = 'Breath'
        if l[i] in ['Da', 'Knife', 'Knive', 'Kn']:
            l[i] = 'Dagger'
        if l[i] == 'To':
            l[i] = 'Tome'
        if l[i] == 'In':
            l[i] = 'Infantry'
        if l[i] in ['Ca', 'Mo', 'Mounted', 'Horse', 'Cav', 'Cavalier']:
            l[i] = 'Cavalry'
        if l[i] in ['Ar', 'Armoured', 'Knight', 'Armour', 'Armor']:
            l[i] = 'Armored'
        if l[i] in ['Fl', 'Flier']:
            l[i] = 'Flying'
        if l[i] in ['Hp', 'Atk', 'Spd', 'Def', 'Res', 'Bst']:
            l[i] = l[i].upper()
        if l[i] == 'Attack':
            l[i] = 'ATK'
        if l[i] == 'Speed':
            l[i] = 'SPD'
        if l[i] == 'Defense':
            l[i] = 'DEF'
        if l[i] == 'Resistance':
            l[i] = 'RES'
        if l[i] in ['Total', 'Stat']:
            l[i] = 'BST'
        if l[i] == 'Na':
            l[i] = 'Name'
        if l[i] == 'Co':
            l[i] = 'Colour'
        if l[i] == 'We':
            l[i] = 'Weapon'
        if l[i] == 'Mov':
            l[i] = 'Movement'
        if '>' in l[i] or '<' in l[i] or '=' in l[i]:
            op = None
            filt = None
            if '>' in l[i] and '>=' not in l[i]:
                # greater than
                filt = l[i].split('>')
                op = operator.gt
            if '>=' in l[i]:
                # greater than or equal
                filt = l[i].split('>=')
                op = operator.ge
            if '<' in l[i] and '<=' not in l[i]:
                # less than
                filt = l[i].split('<')
                op = operator.lt
            if '<=' in l[i]:
                # less than or equal
                filt = l[i].split('<=')
                op = operator.le
            if '=' in l[i] and '!=' not in l[i] and '>=' not in l[i] and '<=' not in l[i]:
                # equal
                filt = l[i].split('=')
                if len(filt) == 3:
                    del filt[1]
                op = operator.eq
            if '!=' in l[i]:
                # not equal
                filt = l[i].split('!=')
                op = operator.ne
            if filt is None or operator is None:
                return None
            if len(filt) != 2:
                return None
            elif filt[0]:
                field, number = filt
            else:
                j=0
                for j in range(1, len(filt[1])):
                    if not filt[1][:j].isdigit():
                        break
                    j += 1
                number = filt[1][:j-1]
                field = filt[1][j-1:]
            field = standardize({'s':field if isinstance(field, list) else [field]}, 's')
            if field:
                if isinstance(field[0], tuple):
                    field = field[0]
                elif field[0] not in ['HP', 'ATK', 'SPD', 'DEF', 'RES', 'BST']:
                    return None
            else:
                return None
            l[i] = (op, field, int(number))
        if '+' in l[i]:
            fields = None
            if ',' in l[i] and '+' not in l[i]:
                fields = l[i].split(',')
            if '+' in l[i] and ',' not in l[i]:
                fields = l[i].split('+')
            if not fields or '' in fields:
                return None
            fields = standardize({'s':fields if isinstance(fields, list) else [fields]}, 's')
            if fields:
                for f in fields:
                    if f not in ['HP', 'ATK', 'SPD', 'DEF', 'RES', 'BST']:
                        return None
            else:
                return None
            l[i] = tuple(fields)
    if k == 'f':
        if bool(set(filter(lambda x:not isinstance(x, tuple), l)) - set(valid_filters)):
            return None
        else:
            colours = list(filter(lambda x:x in ['Red', 'Blue', 'Green', 'Colorless'], l))
            weapons = list(filter(lambda x:x in ['Sword', 'Lance', 'Axe', 'Bow', 'Staff', 'Dagger', 'Breath', 'Tome'], l))
            move = list(filter(lambda x:x in ['Infantry', 'Cavalry', 'Armored', 'Flying'], l))
            thresh = list(filter(lambda x:isinstance(x, tuple), l))
            filters = {}
            if colours:
                filters['Colour'] = colours
            if weapons:
                filters['Weapon'] = weapons
            if move:
                filters['Movement'] = move
            if thresh:
                filters['Threshold'] = thresh
            return filters
    if k == 's' and bool(set(filter(lambda x:not isinstance(x, tuple), l)) - set(valid_sorts)):
        return None
    return l
