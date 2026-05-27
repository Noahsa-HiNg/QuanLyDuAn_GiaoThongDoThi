import psycopg2
import io

def fix_names():
    conn = psycopg2.connect("postgresql://myadmin:123456@localhost:5432/qlda_dothithongminh")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("CREATE TEMP TABLE tmp_districts (id INT, name TEXT, geometry TEXT);")
    cur.execute("CREATE TEMP TABLE tmp_streets (id INT, name TEXT, district_id INT, geometry TEXT, length_km TEXT, max_speed TEXT, is_one_way TEXT);")

    print("Parsing SQL file...")
    with open("load_streets_districts.sql", "r", encoding="utf-8") as f:
        content = f.read()

    # Districts block
    districts_start = content.find("COPY public.districts (id, name, geometry) FROM stdin;")
    if districts_start != -1:
        districts_start = content.find("\n", districts_start) + 1
        districts_end = content.find("\\.", districts_start)
        districts_data = content[districts_start:districts_end]
        
        print("Updating districts...")
        cur.copy_expert("COPY tmp_districts (id, name, geometry) FROM STDIN", io.StringIO(districts_data))
        cur.execute("UPDATE districts SET name = tmp_districts.name FROM tmp_districts WHERE districts.id = tmp_districts.id;")
        print("✅ Updated districts.")

    # Streets block
    streets_start = content.find("COPY public.streets (id, name, district_id, geometry, length_km, max_speed, is_one_way) FROM stdin;")
    if streets_start != -1:
        streets_start = content.find("\n", streets_start) + 1
        streets_end = content.find("\\.", streets_start)
        streets_data = content[streets_start:streets_end]

        print("Updating streets...")
        cur.copy_expert("COPY tmp_streets (id, name, district_id, geometry, length_km, max_speed, is_one_way) FROM STDIN", io.StringIO(streets_data))
        cur.execute("UPDATE streets SET name = tmp_streets.name FROM tmp_streets WHERE streets.id = tmp_streets.id;")
        print("✅ Updated streets.")

    conn.close()

if __name__ == "__main__":
    fix_names()
