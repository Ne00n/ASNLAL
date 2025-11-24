import ipaddress, subprocess, requests, time, re, os
from ipaddress import ip_address, ip_network

class Base:

    def __init__(self,path):
        self.fpingMatch = re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+:.*?min/avg/max\s+=\s+[\d.]+/([\d.]+)/')
        self.path = path

    def call(self,url,method="GET",payload={},headers={},max=5):
        if not headers: headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'}
        allowedCodes, crashed = [200], False
        for run in range(1,max):
            try:
                if method == "POST":
                    req = requests.post(url, json=payload, timeout=(5,5))
                elif method == "GET":
                    req = requests.get(url, headers=headers, timeout=(5,5))
                else:
                    req = requests.patch(url, json=payload, timeout=(5,5))
                if req.status_code in allowedCodes: return True,req
                crashed = False
            except Exception as ex:
                crashed = True
                pass
            if run == 4 and not crashed:
                return False,req
            elif run == 4:
                return False,None
            time.sleep(2)

    def splitTo24(self,subnet):
        network = ipaddress.ip_network(subnet)
        return [str(subnet) for subnet in network.subnets(new_prefix=24)]

    def getIPs(self,subnet):
        network = ipaddress.ip_network(subnet)
        return [str(ip) for ip in network]

    def cmd(self,cmd,timeout=None):
        try:
            p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, timeout=timeout)
            return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]
        except:
            return ["",""]

    def fping(self,targets,pings=1):
        fping = f"fping -c {pings} "
        fping += " ".join(targets)
        result = self.cmd(fping)
        matches = self.fpingMatch.findall(result[1])
        return matches

    def processSubnet(self,row):
        subnet, details, pingable, results = row[0], row[1], row[2], []
        ips = self.getIPs(subnet)
        #print(f"Running fping for {subnet} at .{pingable[0]}")
        for run in range(pingable[0], len(ips), 10):
            batch = ips[run:run+10]
            results += self.fping(batch)
            if not results: continue
            if not "any" in details['settings']: break
        return {subnet:results}

    def processOctet(self,taskID,block):
        seed = {}
        try:
            print(f"Downloading file https://data.serv.app/files/{block[0]}.txt")
            with requests.get(f"https://data.serv.app/files/{block[0]}.txt", stream=True) as response:
                response.raise_for_status()
                with open(f"{self.path}/{block[0]}.txt", 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            subnetOjects = [ip_network(subnet) for subnet in block[1]]
            with open(f"{self.path}/{block[0]}.txt", 'r') as f:
                for line in f:
                    ip = ip_address(line.strip())
                    for subnet in subnetOjects:
                        if str(subnet) in seed and len(seed[str(subnet)]) > 10: continue
                        if ip in subnet:
                            if not str(subnet) in seed: seed[str(subnet)] = []
                            seed[str(subnet)].append(int(str(ip).split(".")[-1]))
                            seed[str(subnet)].sort()
        except Exception as e:
            print(f"Failed to generate seeds: {e}")
        finally:
            if os.path.exists(f"{self.path}/{block[0]}.txt"): os.remove(f"{self.path}/{block[0]}.txt")
            return seed