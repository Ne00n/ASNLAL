from Class.base import Base
import systemd.daemon
import signal, json, time, os

tools = Base()
refresh, shutdown = 0, False

def gracefulExit(signal_number,stack_frame):
    global shutdown
    systemd.daemon.notify('STOPPING=1')
    shutdown = True

path = os.path.dirname(os.path.realpath(__file__))
with open(f"{path}/configs/asn.json") as handle: config =  json.loads(handle.read())

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')

while True:
    if shutdown:
        print("Shutting down gracefully...")
        exit(0)
    if not os.path.isfile(f"{path}/src/table.txt") or os.path.getmtime(f"{path}/src/table.txt") + (60*60*24) < int(time.time()):
        print(f"Fetching bgp.tools/table.txt")
        success, req = tools.call("https://bgp.tools/table.txt")
        if success:
            with open(f"{path}/src/table.txt", 'w') as file: file.write(req.text)
            refresh = 0 #trigger refresh
        elif not success and not os.path.isfile(f"{path}/src/table.txt"): 
            exit("Failed to get table.txt")

    if refresh < int(time.time()):
        print("Updating asn's")
        if config['asnSrc']:
            success, req = tools.call(config['asnSrc'])
            if success:
                config['asnList'] = req.json()
            elif not success:
                print("Failed to fetch asn's")
        refresh = int(time.time()) + (60*60)

        print("Updating sources")
        analyze = {}
        with open(f"{path}/src/table.txt") as file:
            for line in file:
                line = line.rstrip()
                prefix, asn = line.split(" ")
                for selectedASN, settings in config['asnList'].items():
                    if int(asn) == int(selectedASN):
                        if not asn in analyze: analyze[asn] = {}
                        if not prefix in analyze[asn]: analyze[asn][prefix] = {"created":int(time.time()),"updated":0,"settings":settings}
                        break
        
        print("Updating local asn's")
        for asn, data in analyze.items():
            if not os.path.isfile(f"{path}/data/{asn}.json"):
                with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(data, f)
            else:
                with open(f"{path}/data/{asn}.json") as handle: asnData =  json.loads(handle.read())
                for subnet, details in data.items():
                    if not subnet in asnData:
                        print(f"Adding {subnet} to {asn}")
                        asnData[subnet] = details
                for subnet in list(asnData):
                    if not subnet in data:
                        print(f"Deleting {subnet} from {asn}")
                        del asnData[subnet]
                with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnData, f)

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
                        if not "all" in details['settings']: break
                with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnData, f)
                if shutdown:
                    print("Shutting down gracefully...")
                    exit(0)
    time.sleep(2)