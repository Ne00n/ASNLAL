import ipaddress, subprocess, requests, time, re

class Base:

    def __init__(self):
        self.fpingMatch = re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+:.*?min/avg/max\s+=\s+[\d.]+/([\d.]+)/')

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

    def fping(self,targets,pings=3):
        fping = f"fping -c {pings} "
        fping += " ".join(targets)
        result = self.cmd(fping)
        matches = self.fpingMatch.findall(result[1])
        return matches