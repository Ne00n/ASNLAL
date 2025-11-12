from Class.base import Base
import json, os

tools = Base()
path = os.path.dirname(os.path.realpath(__file__))
with open(f"{path}/asn.json") as handle: config =  json.loads(handle.read())
if not os.path.isfile(f"{path}/src/table.txt"):
    success, req = tools.call("https://bgp.tools/table.txt")
    if not success: exit("Failed to get table.txt")
    with open(f"{path}/src/table.txt", 'w') as file: file.write(req.text)
    
analyze = {}
with open(f"{path}/src/table.txt") as file:
    for line in file:
        line = line.rstrip()
        prefix, asn = line.split(" ")
        if int(asn) in config['targets']:
            if not asn in analyze: analyze[asn] = {}
            if not prefix in analyze[asn]: analyze[asn][prefix] = {}

for asn, data in analyze.items():
    if not os.path.isfile(f"{path}/data/{asn}.json"):
        with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(data, f, indent=4)