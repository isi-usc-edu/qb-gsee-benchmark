#make an input json file for miniML.py to digest
import json
import pandas as pd

filename = "Data/Metrics_with_target.csv"
df = pd.read_csv(filename)
features = df.columns[:-3].to_list()
target = df.columns[-1]



# a Python object (dict):
inputForMiniML = {
  "Filename": filename,
  "Features": features,
  "Target": target
}

# convert into JSON:
y = json.dumps(inputForMiniML)

# the result is a JSON string:
print(y)

#save the json file
with open('inputForMiniML.json', 'w', encoding='utf-8') as f:
    json.dump(inputForMiniML, f, ensure_ascii=False, indent=4)