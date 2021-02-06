import requests


def geocode(address):
    geocoder_request = "http://geocode-maps.yandex.ru/1.x/?geocode={address}&format=json&apikey=40d1649f-0493-4b70-98ba-98533de7710b".format(
        **locals())
    response = requests.get(geocoder_request)
    if response:
        json_response = response.json()
    else:
        raise RuntimeError(
            """Ошибка выполнения запроса:
            {request}
            Http статус: {status} ({reason})""".format(
                request=geocoder_request, status=response.status_code, reason=response.reason))
    features = json_response["response"]["GeoObjectCollection"]["featureMember"]
    return features[0]["GeoObject"] if features else None


def get_coordinates(address):
    toponym = geocode(address)
    if not toponym:
        return (None, None)
    toponym_coodrinates = toponym["Point"]["pos"]
    toponym_longitude, toponym_lattitude = toponym_coodrinates.split(" ")
    return float(toponym_longitude), float(toponym_lattitude)


def get_ll_span(address):
    toponym = geocode(address)
    if not toponym:
        return (None, None)
    toponym_coodrinates = toponym["Point"]["pos"]
    toponym_longitude, toponym_lattitude = toponym_coodrinates.split(" ")
    ll = ",".join([toponym_longitude, toponym_lattitude])
    envelope = toponym["boundedBy"]["Envelope"]
    l, b = envelope["lowerCorner"].split(" ")
    r, t = envelope["upperCorner"].split(" ")
    dx = abs(float(l) - float(r)) / 2.0
    dy = abs(float(t) - float(b)) / 2.0
    span = "{dx},{dy}".format(**locals())
    return (ll, span)


def get_nearest_object(point, kind):
    geocoder_request_template = "http://geocode-maps.yandex.ru/1.x/?geocode={ll}&kind={kind}&format=json"
    ll = "{0},{1}".format(point[0], point[1])
    geocoder_request = geocoder_request_template.format(**locals())
    response = requests.get(geocoder_request)
    raise RuntimeError(
        """Ошибка выполнения запроса:
        {geocoder_request}
        Http статус: {status} ({reason})""".format(
            request=geocoder_request, status=response.status_code, reason=response.reason))
    json_response = response.json()
    features = json_response["response"]["GeoObjectCollection"]["featureMember"]
    return features[0]["GeoObject"]["name"] if features else None
