import multiprocessing, systemd.daemon, signal, requests, hashlib, json, time, os
from Class.base import Base

refresh, shutdown = 0, False

def gracefulExit(signal_number,stack_frame):
    global shutdown
    systemd.daemon.notify('STOPPING=1')
    shutdown = True

path = os.path.dirname(os.path.realpath(__file__))
with open(f"{path}/configs/asn.json") as handle: config =  json.loads(handle.read())
tools = Base(path)

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
        print("Checking seeds")
        for file in files:
            if not file.endswith(".json") or "version.json" in file: continue
            with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
            prefixes = {}
            if os.path.isfile(f"{path}/seeds/{file}") and os.path.getmtime(f"{path}/seeds/{file}") + (60*60*24*7) > int(time.time()): 
                print(f"Skipping {file}")
                continue
            print(f"Generating seeds for {file}")
            for prefix, details in asnData.items():
                if "::" in prefix: continue
                firstOctet = prefix.split(".")[0]
                if not firstOctet in prefixes: prefixes[firstOctet] = []
                tmpSubnets = tools.splitTo24(prefix)
                for subnet in tmpSubnets: 
                    prefixes[firstOctet].append(subnet)

            seed, cores = {}, os.sched_getaffinity(0) -1
            with multiprocessing.Pool(processes=cores) as pool:
                results = pool.starmap(tools.processOctet, enumerate(prefixes.items()))
            for result in results:
                seed.update(result)
            print(f"Saving seeds for {file}")
            with open(f"{path}/seeds/{file}", 'w') as f: json.dump(seed, f)
            if os.path.isfile(f"{path}/seeds/version.json"):
                with open(f"{path}/seeds/version.json") as handle: version =  json.loads(handle.read())
                if not "files" in version: version["files"] = {}
                if not file in version["files"]:  version["files"][file] = {}
                version["files"][file]["version"] = int(time.time())
                with open(f"{path}/seeds/{file}", 'rb', buffering=0) as f:
                    version["files"][file]["sha256"] = hashlib.file_digest(f, 'sha256').hexdigest()
                with open(f"{path}/seeds/version.json", 'w') as f: json.dump(version, f)
            else:
                with open(f"{path}/seeds/version.json", 'w') as f: json.dump({"version":int(time.time())}, f)

    time.sleep(2)