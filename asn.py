from Class.base import Base
import os

tools = Base()
path = os.path.dirname(os.path.realpath(__file__))
if not os.path.isfile(f"{path}/data/table.txt"):
    success, req = tools.call("https://bgp.tools/table.txt")
    if not success: exit("Failed to get table.txt")
    with open(f"{path}/data/table.txt", 'w') as file: file.write(req.text)
    
