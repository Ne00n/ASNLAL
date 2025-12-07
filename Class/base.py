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

    def processSubnet(self,data):
        results = []
        ips = self.getIPs(data['subnet'])
        targets = [ips[i] for i in data['pingable'] if i < len(ips)]

        for i in range(0, len(targets), 10):
            batch = targets[i:i+10]
            result = self.fping(batch)
            if not result: continue
            for row in result:
                results.append([row[0].split(".")[-1],float(row[1])])
            if not "any" in data['details']['settings']: break
        return {data['subnet']:results}