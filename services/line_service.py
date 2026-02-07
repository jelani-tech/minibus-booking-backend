from models.transport import Line, Stop

class LineService:
    @staticmethod
    def get_all_lines():
        return Line.query.all()

    @staticmethod
    def get_line_by_id(line_id):
        return Line.query.get(line_id)

    @staticmethod
    def get_stops_by_line_id(line_id):
        return Stop.query.filter_by(line_id=line_id).order_by(Stop.order).all()
