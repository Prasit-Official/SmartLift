import csv

def export_cycles(folder, events):
    with open(folder/"cycles.csv","w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=["rep_id","started","ended","outcome"])
        writer.writeheader(); writer.writerows(events)
