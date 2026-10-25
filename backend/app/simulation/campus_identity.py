"""Authored fictional names and biographies, independent of appearance/behavior.

These small naming-style pools are character-writing material, not ethnicity,
citizenship, language proficiency or OSU demographic labels. Display names are
stored whole; an English-language display order is an authored preference here.
"""
from .world import uniform

IDENTITY_VERSION = "campus-fictional-identity/1"

# Weights are authored cast variety, never inferred population percentages.
NAME_STYLES = {
    "english_language": {
        "weight": 44,
        "given": ("Alex", "Maya", "Sam", "Nora", "Leo", "Ava", "Theo", "Iris", "Eli", "Lena", "Owen", "Zoe",
                  "Kai", "Mila", "Noah", "Ruby", "Finn", "Ada", "Arlo", "Esme", "Jules", "Remy", "Sage", "Robin",
                  "Amelia", "Jordan", "Cameron", "Morgan", "Riley", "Taylor", "Harper", "Daniel", "Claire", "Erin",
                  "Gabriel", "Hannah", "Isaac", "Jasmine", "Julian", "Leah", "Marcus", "Natalie", "Olivia", "Quinn",
                  "Ruth", "Simone", "Thomas", "Vivian", "Walter", "Yvonne", "Evelyn", "Miles", "Naomi", "Caleb"),
        "family": ("Reed", "Foster", "Brooks", "Ellis", "Morgan", "Hayes", "Bennett", "Campbell", "Morris", "Walsh",
                   "Lewis", "Thompson", "Walker", "Carter", "Mitchell", "Parker", "Collins", "Stewart", "Turner", "Brown",
                   "Johnson", "Robinson", "Howard", "Baker", "Hughes", "Kelly", "Murphy", "Davis", "Wright", "Price",
                   "Sullivan", "Richardson", "Grant", "Cooper", "Reynolds", "Bell", "Anderson", "Cox", "Ward", "Young"),
    },
    "south_asian": {
        "weight": 14,
        "given": ("Aarav", "Aditi", "Anaya", "Arjun", "Dev", "Diya", "Ishaan", "Isha", "Kavya", "Kiran", "Meera", "Nikhil",
                  "Neha", "Nisha", "Priya", "Rahul", "Rohan", "Riya", "Saanvi", "Sanjay", "Shreya", "Siddharth", "Tanvi", "Varun",
                  "Vikram", "Anika", "Deepa", "Leela", "Manish", "Mira", "Ravi", "Sonia"),
        "family": ("Patel", "Shah", "Desai", "Mehta", "Joshi", "Rao", "Sharma", "Gupta", "Nair", "Iyer", "Menon", "Kapoor",
                   "Bhat", "Chandra", "Sethi", "Verma", "Trivedi", "Vyas", "Parekh", "Malhotra", "Saxena", "Kulkarni", "Naik", "Bose"),
    },
    "chinese_romanized": {
        "weight": 10,
        "given": ("Ming", "Yue", "Wei", "Yan", "Liang", "Rui", "Jiahao", "Yuxin", "Xinyi", "Wen", "Hao", "Mei",
                  "Jun", "Qing", "Zihan", "Yifan", "Chen", "Xin", "Ning", "Shu", "An", "Shan", "Lin", "Bo"),
        "family": ("Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou", "Xu", "Sun",
                   "Ma", "Zhu", "Hu", "Guo", "He", "Gao", "Lin", "Luo", "Zheng", "Liang", "Xie", "Song"),
    },
    "korean_romanized": {
        "weight": 6,
        "given": ("Minji", "Jisoo", "Hana", "Yuna", "Sora", "Jiwoo", "Seoyeon", "Sujin", "Haeun", "Dahyun", "Nari", "Eunji",
                  "Minho", "Jiho", "Joon", "Hyunwoo", "Seojun", "Doyun", "Jiwon", "Jinwoo", "Taehyun", "Sunwoo", "Yejun", "Junseo"),
        "family": ("Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim", "Han", "Shin", "Seo", "Kwon", "Hwang", "Ahn"),
    },
    "vietnamese_romanized": {
        "weight": 4,
        "given": ("Anh", "Binh", "Chi", "Duc", "Giang", "Ha", "Hanh", "Hieu", "Hoa", "Hoang", "Khanh", "Lan",
                  "Linh", "Mai", "Minh", "Nam", "Ngoc", "Phuong", "Quang", "Thao", "Thien", "Trang", "Trung", "Vy"),
        "family": ("Nguyen", "Tran", "Le", "Pham", "Hoang", "Huynh", "Phan", "Vu", "Vo", "Dang", "Bui", "Do", "Ho", "Ngo", "Duong", "Ly"),
    },
    "spanish_language": {
        "weight": 12,
        "given": ("Adriana", "Alejandro", "Ana", "Camila", "Carlos", "Daniela", "Diego", "Elena", "Emilio", "Gabriela", "Isabel", "Javier",
                  "Joaquin", "Jose", "Julia", "Lucia", "Luis", "Marisol", "Mateo", "Natalia", "Pablo", "Rafael", "Rosa", "Sofia",
                  "Valentina", "Victor", "Alma", "Andres", "Carmen", "Ines", "Lola", "Manuel"),
        "family": ("Rivera", "Santos", "Garcia", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores",
                   "Diaz", "Cruz", "Morales", "Reyes", "Ortiz", "Gutierrez", "Vargas", "Castillo", "Romero", "Alvarez", "Mendoza", "Vega"),
    },
    "arabic_language": {
        "weight": 6,
        "given": ("Amira", "Aya", "Dalia", "Farah", "Hana", "Iman", "Layla", "Lina", "Mariam", "Nadia", "Noor", "Salma",
                  "Adam", "Amir", "Farid", "Hadi", "Karim", "Malik", "Omar", "Rami", "Sami", "Tariq", "Yasin", "Zayd"),
        "family": ("Haddad", "Nasser", "Mansour", "Khalil", "Saleh", "Hamdan", "Darwish", "Najjar", "Khoury", "Awad", "Fadel", "Masri",
                   "Hakim", "Saad", "Shakir", "Hamid", "Barakat", "Farhat", "Karam", "Jaber", "Sabbagh", "Abboud", "Salem", "Sayegh"),
    },
    "yoruba": {
        "weight": 4,
        "given": ("Ayo", "Bola", "Dami", "Eniola", "Femi", "Folake", "Ife", "Kemi", "Lola", "Sade", "Seyi", "Tayo",
                  "Temi", "Tobi", "Tolu", "Wale", "Yemi", "Yetunde", "Bisi", "Bukola", "Dele", "Funmi", "Jide", "Tunde"),
        "family": ("Adeyemi", "Adebayo", "Adediran", "Adekunle", "Adeniyi", "Afolabi", "Ajayi", "Akinyemi", "Akintola", "Bamidele",
                   "Balogun", "Ogunleye", "Ojo", "Oladipo", "Olawale", "Oni", "Onabajo", "Oyeleke", "Salami", "Taiwo"),
    },
}


def naming_style(seed, key):
    draw = uniform(seed, "naming-style", key)*sum(style["weight"] for style in NAME_STYLES.values())
    for name, style in NAME_STYLES.items():
        draw -= style["weight"]
        if draw < 0:
            return name
    return next(iter(NAME_STYLES))


def family_identity(seed, household_id):
    style = naming_style(seed, ("family", household_id))
    names = NAME_STYLES[style]["family"]
    return style, names[int(uniform(seed, "family-name", household_id)*len(names))]


def resident_identity(seed, resident_id, used_names, family=None):
    """Allocate a unique full name without encoding an ethnicity in appearance.

    A minority of fictional residents choose an English-language given name
    alongside another family naming style, as a diaspora/preferred-name option.
    This is intentionally possible; a cross-cultural name is not an error.
    """
    family_style, fixed_family = family or (naming_style(seed, ("resident", resident_id)), None)
    given_style = "english_language" if family_style != "english_language" and uniform(seed, "preferred-given-style", resident_id) < .08 else family_style
    ordered_styles = [given_style, *[key for key in NAME_STYLES if key != given_style]]
    families = (fixed_family,) if fixed_family else NAME_STYLES[family_style]["family"]
    first_family = int(uniform(seed, "family-name", resident_id)*len(families))
    for actual_style in ordered_styles:
        given = NAME_STYLES[actual_style]["given"]
        first_given = int(uniform(seed, "given-name", resident_id, actual_style)*len(given))
        for attempt in range(len(given)*len(families)):
            given_name = given[(first_given+attempt) % len(given)]
            family_name = families[(first_family+attempt//len(given)) % len(families)]
            if given_name.casefold() == family_name.casefold():
                continue
            display_name = f"{given_name} {family_name}"
            if display_name.casefold() not in used_names:
                used_names.add(display_name.casefold())
                return display_name, {"version": IDENTITY_VERSION, "source": "authored_fictional", "given_name": given_name,
                                      "family_name": family_name, "naming_style": family_style, "given_name_style": actual_style,
                                      "display_order": "given_family"}
    raise ValueError("Fictional name vocabulary exhausted")


INTERESTS = ("photography", "reading", "cooking", "cycling", "gardening", "sketching", "live music", "running", "board games", "hiking", "volunteering", "birdwatching")
CHILD_INTERESTS = ("picture books", "building blocks", "drawing", "spotting birds", "puzzles", "story time")
ROLE_BIOGRAPHIES = {
    "student": "An undergraduate balancing classes, study time and campus life.",
    "graduate student": "A graduate student dividing the day between seminars and research.",
    "professor": "A professor with teaching, office hours and work to finish on campus.",
    "staff": "A university staff member fitting errands and lunch around the workday.",
    "caregiver": "A local parent caring for a preschooler and planning a short neighborhood outing.",
    "child": "A preschooler who explores nearby paths with a caregiver.",
    "neighbor": "A neighborhood resident with a few errands and a short afternoon walk.",
}


def biography(seed, resident_id, role):
    interests = CHILD_INTERESTS if role == "child" else INTERESTS
    interest = interests[int(uniform(seed, "resident-interest", resident_id)*len(interests))]
    return f"{ROLE_BIOGRAPHIES[role]} Enjoys {interest}."
