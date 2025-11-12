from fake_useragent import UserAgent
import requests, time

class Base:

    def __init__(self):
        ua = UserAgent()
        self.userAgent = ua.chrome 

    def call(self,url,method="GET",payload={},headers={},max=5):
        if not headers: headers = {'User-Agent':self.userAgent}
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