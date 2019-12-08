# Purpose
The script email2thehive.py reads an email file(.msg/.eml) and creates a new case into an instance of [TheHive](https://thehive-project.org/). If the subject of the mail contains "[ALERT]", an alert is created.

# Configuration
The script is fully configurable via a Python-friendly configuration file. See email2thehive.conf sample for more details.

# Usage
The script can be run manually to import an email file. The syntax is simple:
```
# ./imap2thehive.py -h
usage: imap2thehive.py [-h] [-v] [-c CONFIG] [-f FILEPATH]

Process an email file to create TheHive alerts/cased.

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         verbose output
  -c CONFIG, --config CONFIG
                        configuration file (default: /etc/imap2thehive.conf)
  -f FILEPATH, --file FILEPATH
                        email file path
```

# Observables Whitelisting
The script is able to extract observables (emails, URLs, files, hashes). To avoid too many false positives, it is possible to create whitelists (based on regular expressions). See the file email2thehive.whitelists.
