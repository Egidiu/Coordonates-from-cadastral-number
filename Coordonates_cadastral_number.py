import re
import streamlit as st
import pandas as pd
import requests
import time
from pyproj import Transformer
import io
from streamlit_folium import st_folium
import folium
from streamlit_folium import folium_static

st.set_page_config(layout="wide") #Make page wide

def extract_url_from_html(html):
    match = re.search(r'href="([^"]+)"', html)
    return match.group(1) if match else None

def fetch_json(url):
    """
    Retrieves JSON data from a specified URL.

    Parameters:
    - url (str): The URL from which to fetch the JSON data.

    Returns:
    - dict: The JSON data parsed into a dictionary if the request is successful (HTTP status code 200).
    - None: If the request fails, the function displays an error message and returns None.
    """
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch {url}. Status code: {response.status_code}")
        return None

def convert_coordinates(json_data):
    """
    Takes a JSON object containing geographic data (in the form of GeoJSON) and converts the coordinates of the geometry from the EPSG:3844 coordinate reference system to the EPSG:4326 system (commonly used for latitude-longitude coordinates).

    Parameters:
    - json_data (dict): A dictionary representing the JSON (GeoJSON) data containing geographic features, including coordinates.

    Returns:
    - converted_coordinates (list): A list of coordinates converted to the EPSG:4326 system.
    - central_lat (float): The central latitude of the converted coordinates.
    - central_lon (float): The central longitude of the converted coordinates.

    If `json_data` is empty or invalid, the function returns three None values.
    """
    if json_data:
        transformer = Transformer.from_crs("EPSG:3844", "EPSG:4326", always_xy=True)
        rings = json_data["features"][0]["geometry"]["rings"]
        converted_coordinates = []
        for ring in rings:
            converted_ring = [transformer.transform(x, y) for x, y in ring]
            converted_coordinates.extend(converted_ring)
        central_lat = sum(x for x, y in converted_coordinates) / len(converted_coordinates)
        central_lon = sum(y for x, y in converted_coordinates) / len(converted_coordinates)
        return converted_coordinates, central_lat, central_lon
    else:
        return None, None, None

def display_map(df_output):
    """
    Displays a map based on the selected cadastral number from the provided DataFrame.

    Parameters:
    - df_output (DataFrame): A pandas DataFrame containing cadastral data, including central coordinates, perimeter coordinates, and Google Maps links.

    Functionality:
    1. Provides a radio button to select a cadastral number from the unique values in the DataFrame.
    2. Filters the DataFrame based on the selected cadastral number.
    3. If data is available for the selected number:
    - Extracts the central latitude and longitude.
    - Creates a folium map centered on these coordinates.
    - Adds a marker at the central point.
    - Draws a polygon representing the perimeter using the coordinates from the DataFrame.
    - Displays the map in a Streamlit app.
    - Provides a link to Google Maps for the central point.
    4. If no data is found for the selected cadastral number, displays a message indicating this.

    Returns:
    - None: The function outputs the map and additional information directly in a Streamlit app.
    """
    st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)
    cadastral_number_option = st.radio(
        "Select cadastral number",
        options=df_output['Cadastral number'].unique()
    )

    df_filtered = df_output[df_output['Cadastral number'] == cadastral_number_option]

    if not df_filtered.empty:
        center_lat = df_filtered['Central_Lon'].values[0]
        center_lon = df_filtered['Central_Lat'].values[0]

                # Afișare link Google Maps pentru centrul perimetrului
        google_maps_link = df_filtered['Google Maps Link - Central Point'].values[0]
        
        st.write(f"[Google Maps Link - Central Point]({google_maps_link})")
        
        # Create map
        m = folium.Map(location=[center_lat, center_lon], zoom_start=17)
        
        # Adding a marker to central point
        folium.Marker(
            location=[center_lat, center_lon],
            popup="Center",
            icon=folium.Icon(color="blue")
        ).add_to(m)
        
        # Adding a polygon for perimeter
        coords = df_filtered[['Long', 'Lat']].values.tolist()
        folium.Polygon(
            locations=coords,
            color='green',
            fill=True,
            fill_color='green',
            fill_opacity=0.3
        ).add_to(m)
        
        # Afișarea hărții în Streamlit
        # st_folium(m, width=600, height=400)
        
        folium_static(m, width=1500, height=600)
        
        # # Afișare link Google Maps pentru centrul perimetrului
        # google_maps_link = df_filtered['Google Maps Link - Central Point'].values[0]
        
        # st.write(f"[Google Maps Link - Central Point]({google_maps_link})")
        st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)
    else:
        st.write("No data for selected cadastral number")
        st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)

def create_output_dataframe(df):
    """
    Creates a DataFrame for output with additional columns and formatted data from the input DataFrame.

    Parameters:
    - df (DataFrame): The input DataFrame containing original data, including cadastral information and coordinates.

    Returns:
    - DataFrame: The processed DataFrame with the following columns:
    - 'Judet': County information.
    - 'Comuna': Commune information.
    - 'Nr. Carte Funciara': Cadastral number.
    - 'Lat': Latitude of the perimeter coordinates.
    - 'Long': Longitude of the perimeter coordinates.
    - 'Central_Lat': Central latitude of the cadastral area.
    - 'Central_Lon': Central longitude of the cadastral area.
    - 'Google Maps Link': URL for viewing the perimeter coordinates on Google Maps.
    - 'Google Maps Link - Central Point': URL for viewing the central point on Google Maps.
    """

    # Create a new DataFrame with specific columns from the input DataFrame
    df_output = pd.DataFrame({
        'County': df['County'],
        'Local UAT': df['Local UAT'],
        'Cadastral number': df['Cadastral number'],
        'Converted_Coordinates': df['Converted_Coordinates'],
        'Central_Lat': df['Central_Lat'],
        'Central_Lon': df['Central_Lon']
    })

    # Explode the 'Converted_Coordinates' column to separate rows for each coordinate pair
    df_output = df_output.explode("Converted_Coordinates")

    # Split the 'Converted_Coordinates' column into 'Lat' and 'Long' columns
    df_output[['Lat', 'Long']] = pd.DataFrame(df_output['Converted_Coordinates'].tolist(), index=df_output.index)

    # Drop the 'Converted_Coordinates' column as it is no longer needed
    df_output.drop(["Converted_Coordinates"], axis=1, inplace=True)

    # Create Google Maps links for each perimeter coordinate
    df_output["Google Maps Link"] = "https://maps.google.com/?q=" + df_output["Lat"].astype(str) + "," + df_output["Long"].astype(str)
    
    # Create a Google Maps link for the central point
    df_output["Google Maps Link - Central Point"] = "https://maps.google.com/?q=" + df_output["Central_Lon"].astype(str) + "," + df_output["Central_Lat"].astype(str)

    return df_output

def main():
    file_path = 'localitati_IDs.xlsx'
    data = pd.read_excel(file_path)

    judete = data['Judet'].unique()
    comune = data[['Comuna', 'Judet', 'Comuna_ID', 'Judet_ID']]

    st.title("Perimeter Coordinates and Central Points by Cadastral Data (Romania)")
    st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)

    def get_comune_by_judet(judet):
        return comune[comune['Judet'] == judet]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        selected_judet = st.selectbox("Select County", judete)

    with col2:
        filtered_comune = get_comune_by_judet(selected_judet)
        selected_comuna = st.selectbox("Select local UAT", filtered_comune['Comuna'])

    with col3:
        nr_carte_funciara = st.number_input("Număr Carte Funciara", min_value=0, format="%d")

    with col4:
        success_message = st.empty()

    judet_id = comune[comune['Judet'] == selected_judet]['Judet_ID'].values[0]
    comuna_id = filtered_comune[filtered_comune['Comuna'] == selected_comuna]['Comuna_ID'].values[0]

    link = f"https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/1/query?f=json&outFields=NATIONAL_CADASTRAL_REFERENCE&spatialRel=esriSpatialRelIntersects&where=INSPIRE_ID%20%3D%20%27RO.{judet_id}.{comuna_id}.{nr_carte_funciara}%27"
    
    # Arrange buttons on the same row with some space
    col_add, col_space, col_dummy = st.columns([3, 1, 3])

    with col_add:
        if st.button("Add"):
            if selected_judet and selected_comuna and nr_carte_funciara:
                record = {
                    "Judet": selected_judet,
                    "Judet_ID": judet_id,
                    "Comuna": selected_comuna,
                    "Comuna_ID": comuna_id,
                    "Numar Carte Funciara": nr_carte_funciara,
                    "Link": link
                }
                if 'recorduri' not in st.session_state:
                    st.session_state.recorduri = []

                if record not in st.session_state.recorduri:
                    st.session_state.recorduri.append(record)
                    success_message.success("The data has been successfully added!")
                else:
                    success_message.warning("The record has already been added!")
            else:
                success_message.error("All fields are required!")

    with col_dummy:
        if st.button("Add Dummy Data"):
            if 'recorduri' not in st.session_state:
                st.session_state.recorduri = []

            dummy_records = [
                {
                    "Judet": "Arges",
                    "Judet_ID": 36,  
                    "Comuna": "Ungheni",
                    "Comuna_ID": 19560,  
                    "Numar Carte Funciara": 12476,
                    "Link": "https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/1/query?f=json&outFields=NATIONAL_CADASTRAL_REFERENCE&spatialRel=esriSpatialRelIntersects&where=INSPIRE_ID%20%3D%20%27RO.38.19560.12476%27"
                },
                {
                    "Judet": "Gorj",
                    "Judet_ID": 181,
                    "Comuna": "Pades",
                    "Comuna_ID": 81095,
                    "Numar Carte Funciara": 39107,
                    "Link": "https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/1/query?f=json&outFields=NATIONAL_CADASTRAL_REFERENCE&spatialRel=esriSpatialRelIntersects&where=INSPIRE_ID%20%3D%20%27RO.181.81095.39107%27"
                }
            ]

            for record in dummy_records:
                if record not in st.session_state.recorduri:
                    st.session_state.recorduri.append(record)

            success_message.success("Dummy data has been added!")

    if 'recorduri' in st.session_state and st.session_state.recorduri:
        df = pd.DataFrame(st.session_state.recorduri)

        if 'Link' in df.columns:
            df['Link'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">request_link</a>')

        def delete_record(index):
            st.session_state.recorduri.pop(index)
            st.session_state.recorduri = st.session_state.recorduri
            st.rerun()

        st.write("Records")

        num_columns = 7
        columns = st.columns(num_columns)

        columns[0].write("County")
        columns[1].write("County_ID")
        columns[2].write("Local UAT")
        columns[3].write("Local UAT_ID")
        columns[4].write("Cadastral number")
        columns[5].write("Link")
        columns[6].write("Action")

        for i, row in df.iterrows():
            with columns[0]:
                st.write(row['Judet'])
            with columns[1]:
                st.write(row['Judet_ID'])
            with columns[2]:
                st.write(row['Comuna'])
            with columns[3]:
                st.write(row['Comuna_ID'])
            with columns[4]:
                st.write(row['Numar Carte Funciara'])
            with columns[5]:
                st.markdown(row['Link'], unsafe_allow_html=True)
            with columns[6]:
                if st.button("Delete", key=f"delete_{i}"):
                    delete_record(i)
        st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)
        if st.button("Processing Data"):
            st.write("Processing Data...")
        
            converted_coordinates_list = []
            central_lat_list = []
            central_lon_list = []
            judet_list = []
            comuna_list = []
            nr_carte_funciara_list = []
            unique_coordinates = set()

            for index, row in df.iterrows():
                link = row['Link']
                judet = row['Judet']
                comuna = row['Comuna']
                nr_carte_funciara = row['Numar Carte Funciara']

                url = extract_url_from_html(link)
                if url:
                    json_data = fetch_json(url)
                    if json_data:
                        converted_coordinates, central_lat, central_lon = convert_coordinates(json_data)

                        unique_converted_coordinates = [coord for coord in converted_coordinates if coord not in unique_coordinates]

                        converted_coordinates_list.append(unique_converted_coordinates)
                        central_lat_list.append(central_lat)
                        central_lon_list.append(central_lon)
                        judet_list.append(judet)
                        comuna_list.append(comuna)
                        nr_carte_funciara_list.append(nr_carte_funciara)

                        unique_coordinates.update(unique_converted_coordinates)

                    else:
                        converted_coordinates_list.append(None)
                        central_lat_list.append(None)
                        central_lon_list.append(None)
                        judet_list.append(None)
                        comuna_list.append(None)
                        nr_carte_funciara_list.append(None)
                else:
                    converted_coordinates_list.append(None)
                    central_lat_list.append(None)
                    central_lon_list.append(None)
                    judet_list.append(None)
                    comuna_list.append(None)
                    nr_carte_funciara_list.append(None)
                time.sleep(2) # add a delay between requests

            df_output = create_output_dataframe(pd.DataFrame({
                'County': judet_list,
                'Local UAT': comuna_list,
                'Cadastral number': nr_carte_funciara_list,
                'Converted_Coordinates': converted_coordinates_list,
                'Central_Lat': central_lat_list,
                'Central_Lon': central_lon_list
            }))
            st.session_state.df_output = df_output

    if 'df_output' in st.session_state and st.session_state.df_output is not None:
        display_map(st.session_state.df_output)
        st.write(st.session_state.df_output)
        output_file_path = 'Coordonates.xlsx'
        output_sheet_name = "Output_data"
        buffer = io.BytesIO()
        st.session_state.df_output.to_excel(buffer, sheet_name=output_sheet_name, index=False)
        buffer.seek(0)
        st.download_button(
            label="Download excel file", 
            data=buffer, 
            file_name=output_file_path, 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)
    else:
        st.write("No data available")
        st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)

    st.markdown("<hr style='border: 1px solid lightgray;'>", unsafe_allow_html=True)
    st.write("If you find this useful and would like to connect, please feel free to contact me on [LinkedIn](https://ro.linkedin.com/in/egidiu-diac).")
    st.write("I'm very curious about how you use this data in your applications 😃")

if __name__ == "__main__":
    main()
