import requests


def get_address_from_coords(coords):
    api_server = 'http://geocode-maps.yandex.ru/1.x/'
    params = {
        'apikey': '40d1649f-0493-4b70-98ba-98533de7710b',
        'geocode': ','.join([str(coords[0]), str(coords[1])]),
        'sco': 'latlong',
        'kind': 'house',
        'format': 'json'
    }
    response = requests.get(api_server, params=params)
    if response:
        try:
            json_response = response.json()
            toponym = json_response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
            toponym_address = toponym['metaDataProperty']['GeocoderMetaData']['text']
            return toponym_address
        except Exception as e:
            return 'Ошибка' + str(e)
    else:
        return None
