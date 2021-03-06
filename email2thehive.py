#!/usr/bin/python3
#
# email2thehive.py - Gets an email file and create new cases/alerts in TheHive
#

from __future__ import print_function
from __future__ import unicode_literals
import logging
import logging.config
import argparse
import configparser
import imaplib
import os,sys
import email
import email.header
import gnupg
import io
import chardet
import time,datetime
import json
import requests
import uuid
import tempfile
import re
from email.parser import HeaderParser
import extract_msg

log = ''

try:
    from thehive4py.api import TheHiveApi
    from thehive4py.models import Case, CaseTask, CaseObservable, CustomFieldHelper
    from thehive4py.models import Alert, AlertArtifact
except:
    log.error("Please install thehive4py.")
    sys.exit(1)

__name__       = "email2thehive"

# Default configuration 
args = ''
config = {
    'thehiveURL'         : '',
    'thehiveApiKey'	 : '',
    'thehiveObservables' : False,
    'thehiveWhitelists'  : None,
    'caseTLP'            : '',
    'caseTags'           : ['email'],
    'caseTasks'          : [],
    'caseFiles'          : [],
    'caseTemplate'       : '',
    'alertTLP'           : '',
    'alertTags'          : ['email'],
    'alertKeyword'       : '\S*\[ALERT\]\S*',
    'customObservables'  : {}
}
whitelists = []
def slugify(s):
    '''
    Sanitize filenames
    Source: https://github.com/django/django/blob/master/django/utils/text.py
    '''
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)

def loadWhitelists(filename):
    '''
    Read regex from the provided file, validate them and populate the list
    '''
    if not filename:
        return []

    try:
        lines = [line.rstrip('\n') for line in open(filename)]
    except IOError as e:
        log.error('Cannot read %s: %s' % (filename, e.strerror))
        sys.exit(1)

    i = 1
    w = []
    for l in lines:
        if len(l) > 0:
            if l[0] == '#':
                # Skip comments and empty lines
                continue
            try:
                re.compile(l)
            except re.error:
                log.error('Line %d: Regular expression "%s" is invalid.' % (l, f))
                sys.exit(1)
            i += 1
            w.append(l)
    return w

def isWhitelisted(string):
    '''
    Check if the provided string matches one of the whitelist regexes
    '''
    global whitelists
    found = False
    for w in whitelists:
        if re.search(w, string, re.IGNORECASE):
            found = True
            break
    return found

def searchObservables(buffer, observables):
    '''
    Search for observables in the buffer and build a list of found data
    '''
    # Observable types
    # Source: https://github.com/armbues/ioc_parser/blob/master/iocp/data/patterns.ini
    observableTypes = [
         { 'type': 'filename', 'regex': r'\b([A-Za-z0-9-_\.]+\.(exe|dll|bat|sys|htm|html|js|jar|jpg|png|vb|scr|pif|chm|zip|rar|cab|pdf|doc|docx|ppt|pptx|xls|xlsx|swf|gif))\b' },
         { 'type': 'url',      'regex': r'\b([a-z]{3,}\:\/\/[a-z0-9.\-:/?=&;]{16,})\b' },
         { 'type': 'ip',       'regex': r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b' },
         { 'type': 'fqdn',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){2,}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'domain',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){1}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'mail',   'regex': r'\b([a-z][_a-z0-9-.+]+@[a-z0-9-.]+\.[a-z]+)\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{32}|[A-F0-9]{32})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{40}|[A-F0-9]{40})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{64}|[A-F0-9]{64})\b' }
         ]

    # Add custom observables if any
    for o in config['customObservables']:
        observableTypes.append({ 'type': o, 'regex': config['customObservables'][o] })

    for o in observableTypes:
        for match in re.findall(o['regex'], buffer, re.MULTILINE|re.IGNORECASE):
            # Bug: If match is a tuple (example for domain or fqdn), use the 1st element
            if type(match) is tuple:
                match = match[0]
            observables.append({ 'type': o['type'], 'value': match })
    return observables

def readMsg(emailFilePath):
    message = extract_msg.Message(emailFilePath)

    fromField = message.sender
    subjectField = message.subject
    log.info("From: %s Subject: %s" % (fromField, subjectField))

    attachments = []
    observables = []

    # Extract SMTP headers and search for observables
    headers = message.header
    headers_string = ''
    i = 0
    while  i < len(headers.keys()):
        headers_string = headers_string + headers.keys()[i] + ': ' + headers.values()[i] + '\n'
        i+=1
    # Temporary disabled
    # observables = searchObservables(headers_string, observables)

    clientIp = ''
    if 'designates ' in message.header['Received-SPF']:
        clientIp = message.header['Received-SPF'].split('designates ', maxsplit=1)[-1].split(maxsplit=1)[0]
    elif 'designate ' in message.header['Received-SPF']:
        clientIp = message.header['Received-SPF'].split('designate ', maxsplit=1)[-1].split(maxsplit=1)[0]

    receivedMail = re.search('<(.*)>', message.sender).group(1)

    spf = clientIp + '|' + receivedMail


    body = ''
    if message.body != None:
        body = message.body
        observables.extend(searchObservables(body, observables))
    elif message.htmlBody != None:
        html = message.htmlBody
        observables.extend(searchObservables(html, observables))
    
    for attachment in message.attachments:
        log.info("Found attachment: %s " % (attachment.longFilename))
        fname, fextension = os.path.splitext(attachment.longFilename)
        fd, path = tempfile.mkstemp(prefix=slugify(fname) + "_", suffix=fextension)
        try:
            with os.fdopen(fd, 'w+b') as tmp:
                tmp.write(attachment.data)
            attachments.append(path)
        except OSerror as e:
            log.error("Cannot dump attachment to %s: %s" % (path,e.errno))
            return False

    observables.append({ 'type': 'other', 'value': spf })

    return fromField, subjectField, observables, body, attachments


def readEml(emailFilePath):
    message = open(emailFilePath, "rb").read()

    # Decode email
    msg = email.message_from_bytes(message)
    decode = email.header.decode_header(msg['From'])[0]
    if decode[1] is not None:
        fromField = decode[0].decode(decode[1])
    else:
        fromField = str(decode[0])
    decode = email.header.decode_header(msg['Subject'])[0]
    if decode[1] is not None:
        subjectField = decode[0].decode(decode[1])
    else:
        subjectField = str(decode[0])
    decode = email.header.decode_header(msg['Received-SPF'])[0]
    if decode[1] is not None:
        if 'designates ' in decode[0].decode(decode[1]):
            clientIp = decode[0].decode(decode[1]).split('designates ', maxsplit=1)[-1].split(maxsplit=1)[0]
        elif 'designate ' in decode[0].decode(decode[1]):
            clientIp = decode[0].decode(decode[1]).split('designate ', maxsplit=1)[-1].split(maxsplit=1)[0]
    else:
        if 'designates ' in str(decode[0]):
            clientIp = str(decode[0]).split('designates ', maxsplit=1)[-1].split(maxsplit=1)[0]
        elif 'designate ' in str(decode[0]):
            clientIp = str(decode[0]).split('designate ', maxsplit=1)[-1].split(maxsplit=1)[0]
    log.info("From: %s Subject: %s" % (fromField, subjectField))

    attachments = []
    observables = []

    # Extract SMTP headers and search for observables
    parser = HeaderParser()
    headers = parser.parsestr(msg.as_string())
    headers_string = ''
    i = 0
    while  i < len(headers.keys()):
        headers_string = headers_string + headers.keys()[i] + ': ' + headers.values()[i] + '\n'
        i+=1
    # Temporary disabled
    # observables = searchObservables(headers_string, observables)

    body = ''
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                body = part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                body = part.get_payload(decode=True).decode('ISO-8859-1')
            observables.extend(searchObservables(body, observables))
        elif part.get_content_type() == "text/html":
            try:
                html = part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                html = part.get_payload(decode=True).decode('ISO-8859-1')
            observables.extend(searchObservables(html, observables))
        else:
            # Extract MIME parts
            filename = part.get_filename()
            mimetype = part.get_content_type()
            if filename and mimetype:
                if mimetype in config['caseFiles'] or not config['caseFiles']:
                    log.info("Found attachment: %s (%s)" % (filename, mimetype))
                    # Decode the attachment and save it in a temporary file
                    charset = part.get_content_charset()
                    if charset is None:
                        charset = chardet.detect(bytes(part))['encoding']
                    # Get filename extension to not break TheHive analysers (see Github #11)
                    fname, fextension = os.path.splitext(filename)
                    fd, path = tempfile.mkstemp(prefix=slugify(fname) + "_", suffix=fextension)
                    try:
                        with os.fdopen(fd, 'w+b') as tmp:
                            tmp.write(part.get_payload(decode=1))
                        attachments.append(path)
                    except OSerror as e:
                        log.error("Cannot dump attachment to %s: %s" % (path,e.errno))
                        return False

    receivedMail = re.search('<(.*)>', fromField).group(1)

    spf = clientIp + '|' + receivedMail

    observables.append({ 'type': 'other', 'value': spf })

    return fromField, subjectField, observables, body, attachments

def submitTheHive(emailFilePath):

    '''
    Create a new case in TheHive based on the email
    Return 'TRUE' is successfully processed otherwise 'FALSE'
    '''
    

    global log

    mailName, mailType = os.path.splitext(emailFilePath)

    if mailType == ".msg":
        fromField, subjectField, observables, body, attachments = readMsg(emailFilePath)
    elif mailType == ".eml":
        fromField, subjectField, observables, body, attachments = readEml(emailFilePath)

    # Cleanup observables (remove duplicates)
    new_observables = []
    for o in observables:
        if not {'type': o['type'], 'value': o['value'] } in new_observables:
            # Is the observable whitelisted?
            if isWhitelisted(o['value']):
                log.debug('Skipping whitelisted observable: %s' % o['value'])
            else:
                new_observables.append({ 'type': o['type'], 'value': o['value'] })
                log.debug('Found observable %s: %s' % (o['type'], o['value']))
        else:
            log.info('Ignoring duplicate observable: %s' % o['value'])
    log.info("Removed duplicate observables: %d -> %d" % (len(observables), len(new_observables)))
    observables = new_observables

    api = TheHiveApi(config['thehiveURL'], config['thehiveApiKey'])

    # Search for interesting keywords in subjectField:
    log.debug("Searching for %s in '%s'" % (config['alertKeywords'], subjectField))
    if re.match(config['alertKeywords'], subjectField, flags=0):
        #
        # Add observables found in the mail body
        #
        artifacts = []
        if config['thehiveObservables'] and len(observables) > 0:
            for o in observables:
                artifacts.append(AlertArtifact(dataType=o['type'], data=o['value']))

        #
        # Prepare tags - add alert keywords found to the list of tags
        #
        tags = list(config['alertTags'])
        match = re.findall(config['alertKeywords'], subjectField)
        for m in match:
            tags.append(m)

        #
        # Prepare the alert
        #
        sourceRef = str(uuid.uuid4())[0:6]
        alert = Alert(title=subjectField.replace('[ALERT]', ''),
                      tlp         = int(config['alertTLP']),
                      tags        = tags,
                      description = body,
                      type        = 'external',
                      source      = fromField,
                      sourceRef   = sourceRef,
                      artifacts   = artifacts)

        # Create the Alert
        id = None
        response = api.create_alert(alert)
        if response.status_code == 201:
            log.info('Created alert %s' % response.json()['sourceRef'])
        else:
            log.error('Cannot create alert: %s (%s)' % (response.status_code, response.text))
            return False

    else:
        # Prepare the sample case
        tasks = []
        for task in config['caseTasks']:
             tasks.append(CaseTask(title=task))

        # Prepare the custom fields
        customFields = CustomFieldHelper()\
            .add_string('from', fromField)\
            .add_string('attachment', str(attachments))\
            .build()

        # If a case template is specified, use it instead of the tasks
        if len(config['caseTemplate']) > 0:
            case = Case(title=subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        template     = config['caseTemplate'],
                        customFields = customFields)
        else:
            case = Case(title        = subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        tasks        = tasks,
                        customFields = customFields)

        # Create the case
        id = None
        response = api.create_case(case)
        if response.status_code == 201:
            newID = response.json()['id']
            log.info('Created case %s' % response.json()['caseId'])
            if len(attachments) > 0:
                for path in attachments:
                    observable = CaseObservable(dataType='file',
                        data    = [path],
                        tlp     = int(config['caseTLP']),
                        ioc     = False,
                        tags    = config['caseTags'],
                        message = 'Found as email attachment'
                        )
                    response = api.create_case_observable(newID, observable)
                    if response.status_code == 201:
                        log.info('Added observable %s to case ID %s' % (path, newID))
                        os.unlink(path)
                    else:
                        log.warning('Cannot add observable: %s - %s (%s)' % (path, response.status_code, response.text))
            #
            # Add observables found in the mail body
            #
            if config['thehiveObservables'] and len(observables) > 0:
                for o in observables:
                    observable = CaseObservable(
                        dataType = o['type'],
                        data     = o['value'],
                        tlp      = int(config['caseTLP']),
                        ioc      = False,
                        tags     = config['caseTags'],
                        message  = 'Found in the email body'
                        )
                    response = api.create_case_observable(newID, observable)
                    if response.status_code == 201:
                        log.info('Added observable %s: %s to case ID %s' % (o['type'], o['value'], newID))
                    else:
                         log.warning('Cannot add observable %s: %s - %s (%s)' % (o['type'], o['value'], response.status_code, response.text))
        
            #
            # Add also email file as observable
            #
            observable = CaseObservable(dataType='file',
                            data    = [emailFilePath],
                            tlp     = int(config['caseTLP']),
                            ioc     = False,
                            tags    = config['caseTags'],
                            message = 'Email file'
                            )
            response = api.create_case_observable(newID, observable)
            if response.status_code == 201:
                log.info('Added observable %s to case ID %s' % (emailFilePath, newID))
                # os.unlink(emailFilePath)
            else:
                log.warning('Cannot add observable: %s - %s (%s)' % (emailFilePath, response.status_code, response.text))

        else:
            log.error('Cannot create case: %s (%s)' % (response.status_code, response.text))
            return False
    return True


def main():
    global args
    global config
    global whitelists
    global log

    parser = argparse.ArgumentParser(
        description = 'Process an email file to create TheHive alerts/cased.')
    parser.add_argument('-v', '--verbose',
        action = 'store_true',
        dest = 'verbose',
        help = 'verbose output',
        default = False)
    parser.add_argument('-c', '--config',
        dest = 'configFile',
        help = 'configuration file (default: /etc/email2thehive.conf)',
        metavar = 'CONFIG')
    parser.add_argument('-f', '--file',
        dest = 'filePath',
        help = 'email file path')
    args = parser.parse_args()

    # Default values
    if not args.configFile:
        args.configFile = '/etc/email2thehive.conf'
    if not args.verbose:
        args.verbose = False

    if not os.path.isfile(args.configFile):
        log.error('Configuration file %s is not readable.' % args.configFile)
        sys.exit(1);

    try:
        c = configparser.ConfigParser()
        c.read(args.configFile)
    except OSerror as e:
        log.error('Cannot read config file %s: %s' % (args.configFile, e.errno))
        sys.exit(1)

    logging.config.fileConfig(args.configFile)

    if args.verbose:
        root_logger = logging.getLogger('root')
        root_logger.setLevel(logging.DEBUG)

    log = logging.getLogger(__name__)

    # TheHive Config
    config['thehiveURL']        = c.get('thehive', 'url')
    config['thehiveApiKey']     = c.get('thehive', 'apikey')
    if c.has_option('thehive', 'observables'):
        value = c.get('thehive', 'observables')
        if value == '1' or value == 'true' or value == 'yes':
            config['thehiveObservables'] = True
    if c.has_option('thehive', 'whitelists'):
        config['thehiveWhitelists'] = c.get('thehive', 'whitelists')

    # New case config
    config['caseTLP']           = c.get('case', 'tlp')
    config['caseTags']          = c.get('case', 'tags').split(',')
    if c.has_option('case', 'tasks'):
        config['caseTasks']     = c.get('case', 'tasks').split(',')
    if c.has_option('case', 'template'):
        config['caseTemplate']  = c.get('case', 'template')
    if c.has_option('case', 'files'):
        config['caseFiles']     = c.get('case', 'files').split(',')

    # Get custom observables if any
    for o in c.options("custom_observables"):
        # Validate the regex
        config['customObservables'][o] = c.get("custom_observables", o)
        try:
            re.compile(config['customObservables'][o])
        except re.error:
            log.error('Regular expression "%s" is invalid.' % config['customObservables'][o])
            sys.exit(1)

    # Issue a warning of both tasks & template are defined!
    if len(config['caseTasks']) > 0 and config['caseTemplate'] != '':
        log.warning('Both case template and tasks are defined. Template (%s) will be used.' % config['caseTemplate'])

    # New alert config
    config['alertTLP']          = c.get('alert', 'tlp')
    config['alertTags']         = c.get('alert', 'tags').split(',')
    if c.has_option('alert', 'keywords'):
        config['alertKeywords'] = c.get('alert', 'keywords')
    # Validate the keywords regex
    try:
        re.compile(config['alertKeywords'])
    except re.error:
        log.error('Regular expression "%s" is invalid.' % config['alertKeywords'])
        sys.exit(1)

    # Validate whitelists
    whitelists = loadWhitelists(config['thehiveWhitelists'])

    print(submitTheHive(args.filePath))
    return

if __name__ == 'email2thehive':
    main()
    sys.exit(0)
