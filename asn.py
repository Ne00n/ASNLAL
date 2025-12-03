import multiprocessing as mp, systemd.daemon, hashlib, signal, json, time, os
from Class.base import Base

refresh, shutdown = 0, False

def gracefulExit(signal_number,stack_frame):
    global shutdown
    systemd.daemon.notify('STOPPING=1')
    shutdown = True

def initWorker(subnets):
    global sharedSubnets
    sharedSubnets = subnets

def sliceWorker(index):
    global sharedSubnets
    data = sharedSubnets[index]
    print(f"Processing {data['subnet']} on index {index}")
    try:
        workerTools = Base(path)
        return workerTools.processSubnet(data)
    except Exception as e:
        print(f"Error processing subnet {data['subnet']} on index {index}: {e}")
        return {data['subnet']: []}

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
                        if not prefix in analyze[asn]: analyze[asn][prefix] = {"created":int(time.time()),"updated":0,"settings":settings,"data":{}}
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

        subnets, mapping = [], {}
        files = os.listdir(f"{path}/data/")
        for file in files:
            if not file.endswith(".json") or "version.json" in file or "status.json" in file: continue
            print(f"Loading {file}")
            with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
            success, req = tools.call(f"https://routing.serv.app/seeds/{file}")
            if not success: continue
            pingable = req.json()
            for prefix, details in asnData.items():
                #ignore ipv6 for now
                if "::" in prefix: continue
                if details['updated'] > int(time.time()): continue
                tmpSubnets = tools.splitTo24(prefix)
                for subnet in tmpSubnets: 
                    if not subnet in pingable: 
                        #print(f"Skipping {subnet}, not pingable")
                        continue
                    subnets.append({"subnet":subnet,"details":details,"pingable":pingable[subnet]})
                #print(f"{prefix} splitted into {len(tmpSubnets)} subnet(s)")
                for subnet in tmpSubnets: 
                    mapping[subnet] = {"file":file,"prefix":prefix}
            print(f"Loaded {file}")
            #do one file at a time
            if subnets: break

        print(f"Running {file} with {len(subnets)} subnets")
        done, start = 0, int(time.time())
        if os.path.exists(f"{path}/results.jsonl"): os.remove(f"{path}/results.jsonl")
        with mp.Pool(processes=4,initializer=initWorker,initargs=(subnets,),maxtasksperchild=1000,) as pool:
            with open(f"{path}/results.jsonl", 'a') as writer:
                for result in pool.imap_unordered(sliceWorker, range(len(subnets))):
                    writer.write(json.dumps(result) + '\n')
                    done += 1
                    if done % 10 == 0:
                        with open(f"{path}/data/status.json", 'w') as f: json.dump({"start":start,"update":int(time.time()),"done":done,"total":len(subnets)}, f)

        toWrite = {}
        with open(f"{path}/results.jsonl", 'r') as results:
            for line in results:
                row = json.loads(line)
                for subnet,pings in row.items():
                    info = mapping[subnet]
                    if not info['file'] in toWrite: toWrite[info['file']] = {}
                    if not info['prefix'] in toWrite[info['file']]: toWrite[info['file']][info['prefix']] = []
                    toWrite[info['file']][info['prefix']].append((subnet,pings))
        
        if os.path.exists(f"{path}/results.jsonl"): os.remove(f"{path}/results.jsonl")

        for file, data in toWrite.items():
            print(f"Writing file {file}")
            with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
            for prefix, subnets in data.items():
                asnData[prefix]['updated'] = int(time.time()) + (60*60*24*7)
                if not "subnets" in asnData[prefix]: asnData[prefix]['data'] = {}
                for row in subnets:
                    if not subnet in asnData[prefix]['data']: asnData[prefix]['data'][row[0]] = []
                    asnData[prefix]['data'][row[0]] += row[1]
            with open(f"{path}/data/{file}", 'w') as f: json.dump(asnData, f)
            if os.path.isfile(f"{path}/data/version.json"):
                with open(f"{path}/data/version.json") as handle: version =  json.loads(handle.read())
                if not "files" in version: version["files"] = {}
                if not file in version["files"]:  version["files"][file] = {}
                version["files"][file]["version"] = int(time.time())
                with open(f"{path}/data/{file}", 'rb', buffering=0) as f:
                    version["files"][file]["sha256"] = hashlib.file_digest(f, 'sha256').hexdigest()
                with open(f"{path}/data/version.json", 'w') as f: json.dump(version, f)
            else:
                with open(f"{path}/data/version.json", 'w') as f: json.dump({"version":int(time.time())}, f)
            refresh = int(time.time())
        
        toWrite = {}
        print(f"Loop done")
        with open(f"{path}/data/status.json", 'w') as f: json.dump({"start":-1,"update":int(time.time()),"done":-1,"total":-1}, f)
    time.sleep(2)