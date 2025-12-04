"""
Utility functions for all importers
"""


def make_labID(db, date) -> str:
    """
    Generate a lab ID for a new sample based on the date of the analysis
    """
    year = str(date.year)[-2:]
    # Query database for all lab IDs
    all_IDs = get_existing_lab_ids(db)
    # Isolate lab IDs from the same year
    same_year = [i for i in all_IDs if year + "-" in i]
    # Get the highest numbered analysis for the year and add 1
    if len(same_year) > 0:
        max_num = max([int(i.split("-")[1]) for i in same_year])
    else:
        max_num = 0
    # Combine year and analysis number to get lab_id
    return construct_lab_id(year, max_num)


def construct_lab_id(year, max_num):
    """
    Generate a lab ID for a new sample based on the date of the analysis
    """
    lab_id = year + "-" + f"{max_num:05d}"
    print(lab_id)
    return lab_id


def get_existing_lab_ids(db):
    return [
        el
        for tup in db.session.query(db.model.sample.lab_id).all()
        for el in tup
        if el is not None
    ]


def find_datum(db, lab_id, datum_param, datum_unit=None):
    Session = db.model.session
    Sample = db.model.sample
    Analysis = db.model.analysis
    Datum = db.model.datum
    DatumType = db.model.datum_type

    query = (
        db.session.query(Datum)
        .join(Analysis)
        .join(Session)
        .join(Sample)
        .join(DatumType)
        .filter(Sample.lab_id == lab_id)
        .filter(DatumType.parameter == datum_param)
    )

    if datum_unit:
        return query.filter(DatumType.unit == datum_unit).first()
    else:
        return query.first()


def find_attribute(db, lab_id, attr_name, analysis_type=None):
    Sample = db.model.sample
    Session = db.model.session
    Analysis = db.model.analysis
    Attribute = db.model.attribute

    query = (
        db.session.query(Attribute)
        .join(Analysis, Attribute.analysis_collection)
        .join(Session)
        .join(Sample)
        .filter(Sample.lab_id == lab_id)
        .filter(Attribute.parameter == attr_name)
    )

    if analysis_type is not None:
        return query.filter(Analysis.analysis_type == analysis_type).first()
    else:
        return query.first()
