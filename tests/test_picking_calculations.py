# Add plugins to sys.path
from pathlib import Path
from uuid import uuid4
from pandas import read_excel

from plugins.import_data.pickingImport import read_picking_data, get_picking_specs

picking_data = Path(__file__).parent.parent/"test_data"

def random_lab_id(date) -> str:
    return uuid4().hex[:6]

def test_picking_data():
    """Basic test of reading picking data"""
    specs = get_picking_specs()
    fn = picking_data/"PickingData"/"Test_Picking_Sheet.xlsx"
    res = list(read_picking_data(fn, specs, random_lab_id))
    assert len(res) == 8

    assert len(res[0]["lab_id"]) == 6

    # Check that the first row is correct

    # Load results table
    res1 = read_pub_table(picking_data/"ExportPublicationTable"/"Test_Results_Table_new.xlsx")
    assert len(res1) == 8

    # Get names from picking input
    names = set([x["name"] for x in res])
    # new names
    new_names = set(res1.iloc[:,0])

    # Check that the names are the same
    assert names == new_names



def read_pub_table(fn):
    tbl = read_excel(fn, skiprows=1, engine="openpyxl")

    # Remove all rows after the last empty row
    last_empty = tbl[tbl.iloc[:,0].isna()].index[0]
    tbl = tbl.iloc[:last_empty]
    # Interpret all rows with only one value as sample IDs, and append them to the grain indexes
    curr_prefix = ""
    for i, row in tbl.iterrows():
        if len(row.dropna()) == 1:
            curr_prefix = f"{row[0]}_"
        else:
            tbl.iloc[i,0] = curr_prefix+tbl.iloc[i,0]

    # Drop rows with data only in first column
    tbl = tbl.dropna(subset=[tbl.columns[1]])

    return tbl
