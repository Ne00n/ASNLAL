from Class.base import Base
import json, time, os

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
        if int(asn) in config['asnList']:
            if not asn in analyze: analyze[asn] = {}
            if not prefix in analyze[asn]: analyze[asn][prefix] = {"created":int(time.time()),"updated":0}

for asn, data in analyze.items():
    if not os.path.isfile(f"{path}/data/{asn}.json"):
        with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(data, f)

files = os.listdir(f"{path}/data/")
for file in files:
    if not file.endswith(".json"): continue
    with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
    for prefix, details in asnData.items():
        #ignore ipv6 for now
        if "::" in prefix: continue
        if details['updated'] > int(time.time()): continue
        print(f"Analyzing {prefix}")
        subnets = tools.splitTo24(prefix)
        print(f"{prefix} splitted into {len(subnets)} subnet(s)")
        for subnet in subnets:
            print(f"Trying to find pingable IPs in {subnet}")
            ips = tools.getIPs(subnet)
            for run in range(0, len(ips), 10):
                batch = ips[run+1:run+11]
                results = tools.fping(batch)
                asnData[prefix]['updated'] = int(time.time()) + (60*60*24*7)
                if not results: continue
                if not subnet in asnData[prefix]: asnData[prefix][subnet] = []
                asnData[prefix][subnet] = results
                break
        with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnData, f)