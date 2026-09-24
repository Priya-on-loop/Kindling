"""
Official BLS SOC 2018 major and minor group titles — a public,
published classification standard (https://www.bls.gov/soc/), not an
invented taxonomy. Only entries that actually appear among our 923
occupations (Outputs/career_graph.json) are included, verified against
the real O*NET-SOC codes present in that file.

If a minor-group code is ever encountered that isn't in
MINOR_GROUP_TITLES (e.g. the occupation dataset is refreshed later),
minor_title() falls back to the major group's own title rather than
guessing at a name — never a fabricated minor-group label.
"""

MAJOR_GROUP_TITLES = {
    "11": "Management Occupations",
    "13": "Business and Financial Operations Occupations",
    "15": "Computer and Mathematical Occupations",
    "17": "Architecture and Engineering Occupations",
    "19": "Life, Physical, and Social Science Occupations",
    "21": "Community and Social Service Occupations",
    "23": "Legal Occupations",
    "25": "Educational Instruction and Library Occupations",
    "27": "Arts, Design, Entertainment, Sports, and Media Occupations",
    "29": "Healthcare Practitioners and Technical Occupations",
    "31": "Healthcare Support Occupations",
    "33": "Protective Service Occupations",
    "35": "Food Preparation and Serving Related Occupations",
    "37": "Building and Grounds Cleaning and Maintenance Occupations",
    "39": "Personal Care and Service Occupations",
    "41": "Sales and Related Occupations",
    "43": "Office and Administrative Support Occupations",
    "45": "Farming, Fishing, and Forestry Occupations",
    "47": "Construction and Extraction Occupations",
    "49": "Installation, Maintenance, and Repair Occupations",
    "51": "Production Occupations",
    "53": "Transportation and Material Moving Occupations",
}

MINOR_GROUP_TITLES = {
    "11-1": "Top Executives",
    "11-2": "Advertising, Marketing, Promotions, Public Relations, and Sales Managers",
    "11-3": "Operations Specialties Managers",
    "11-9": "Other Management Occupations",
    "13-1": "Business Operations Specialists",
    "13-2": "Financial Specialists",
    "15-1": "Computer Occupations",
    "15-2": "Mathematical Science Occupations",
    "17-1": "Architects, Surveyors, and Cartographers",
    "17-2": "Engineers",
    "17-3": "Drafters, Engineering Technicians, and Mapping Technicians",
    "19-1": "Life Scientists",
    "19-2": "Physical Scientists",
    "19-3": "Social Scientists and Related Workers",
    "19-4": "Life, Physical, and Social Science Technicians",
    "19-5": "Occupational Health and Safety Specialists and Technicians",
    "21-1": "Counselors, Social Workers, and Other Community and Social Service Specialists",
    "21-2": "Religious Workers",
    "23-1": "Lawyers, Judges, and Related Workers",
    "23-2": "Legal Support Workers",
    "25-1": "Postsecondary Teachers",
    "25-2": "Preschool, Elementary, Middle, Secondary, and Special Education Teachers",
    "25-3": "Other Teachers and Instructors",
    "25-4": "Librarians, Curators, and Archivists",
    "25-9": "Other Educational Instruction and Library Workers",
    "27-1": "Art and Design Workers",
    "27-2": "Entertainers and Performers, Sports and Related Workers",
    "27-3": "Media and Communication Workers",
    "27-4": "Media and Communication Equipment Workers",
    "29-1": "Healthcare Diagnosing or Treating Practitioners",
    "29-2": "Health Technologists and Technicians",
    "29-9": "Other Healthcare Practitioners and Technical Occupations",
    "31-1": "Home Health, Personal Care, and Nursing Assistants",
    "31-2": "Occupational and Physical Therapist Assistants and Aides",
    "31-9": "Other Healthcare Support Occupations",
    "33-1": "Supervisors of Protective Service Workers",
    "33-2": "Firefighting and Prevention Workers",
    "33-3": "Law Enforcement Workers",
    "33-9": "Other Protective Service Workers",
    "35-1": "Supervisors of Food Preparation and Serving Workers",
    "35-2": "Cooks and Food Preparation Workers",
    "35-3": "Food and Beverage Serving Workers",
    "35-9": "Other Food Preparation and Serving Related Workers",
    "37-1": "Supervisors of Building and Grounds Cleaning and Maintenance Workers",
    "37-2": "Building Cleaning and Pest Control Workers",
    "37-3": "Grounds Maintenance Workers",
    "39-1": "Supervisors of Personal Care and Service Workers",
    "39-2": "Animal Care and Service Workers",
    "39-3": "Entertainment Attendants and Related Workers",
    "39-4": "Funeral Service Workers",
    "39-5": "Personal Appearance Workers",
    "39-6": "Baggage Porters, Bellhops, and Concierges",
    "39-7": "Tour and Travel Guides",
    "39-9": "Other Personal Care and Service Workers",
    "41-1": "Supervisors of Sales Workers",
    "41-2": "Retail Sales Workers",
    "41-3": "Sales Representatives, Services",
    "41-4": "Sales Representatives, Wholesale and Manufacturing",
    "41-9": "Other Sales and Related Workers",
    "43-1": "Supervisors of Office and Administrative Support Workers",
    "43-2": "Communications Equipment Operators",
    "43-3": "Financial Clerks",
    "43-4": "Information and Record Clerks",
    "43-5": "Material Recording, Scheduling, Dispatching, and Distributing Workers",
    "43-6": "Secretaries and Administrative Assistants",
    "43-9": "Other Office and Administrative Support Workers",
    "45-1": "Supervisors of Farming, Fishing, and Forestry Workers",
    "45-2": "Agricultural Workers",
    "45-3": "Fishing and Hunting Workers",
    "45-4": "Forest, Conservation, and Logging Workers",
    "47-1": "Supervisors of Construction and Extraction Workers",
    "47-2": "Construction Trades Workers",
    "47-3": "Helpers, Construction Trades",
    "47-4": "Other Construction and Related Workers",
    "47-5": "Extraction Workers",
    "49-1": "Supervisors of Installation, Maintenance, and Repair Workers",
    "49-2": "Electrical and Electronic Equipment Mechanics, Installers, and Repairers",
    "49-3": "Vehicle and Mobile Equipment Mechanics, Installers, and Repairers",
    "49-9": "Other Installation, Maintenance, and Repair Occupations",
    "51-1": "Supervisors of Production Workers",
    "51-2": "Assemblers and Fabricators",
    "51-3": "Food Processing Workers",
    "51-4": "Metal Workers and Plastic Workers",
    "51-5": "Printing Workers",
    "51-6": "Textile, Apparel, and Furnishings Workers",
    "51-7": "Woodworkers",
    "51-8": "Plant and System Operators",
    "51-9": "Other Production Occupations",
    "53-1": "Supervisors of Transportation and Material Moving Workers",
    "53-2": "Air Transportation Workers",
    "53-3": "Motor Vehicle Operators",
    "53-4": "Rail Transportation Workers",
    "53-5": "Water Transportation Workers",
    "53-6": "Other Transportation Workers",
    "53-7": "Material Moving Workers",
}


def major_group(soc_id: str) -> str:
    """'15-2041.00' -> '15'"""
    return soc_id[:2]


def minor_group(soc_id: str) -> str:
    """'15-2041.00' -> '15-2'"""
    return soc_id[:4]


def broad_group(soc_id: str) -> str:
    """'15-2041.00' -> '15-204'"""
    return soc_id[:6]


def major_title(code: str) -> str:
    return MAJOR_GROUP_TITLES.get(code, "General Occupations")


def minor_title(code: str) -> str:
    if code in MINOR_GROUP_TITLES:
        return MINOR_GROUP_TITLES[code]
    return major_title(code[:2])
