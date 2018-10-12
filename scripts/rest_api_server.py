import datetime
import decimal
import os
import simplejson as json
import uuid
import operator

from flask import Flask
from flask_restplus import Api, Resource, reqparse
from sqlalchemy import inspect
from werkzeug.contrib.fixers import ProxyFix

from atm import PROJECT_ROOT
from atm.database import Database
from atm.config import load_config


def set_up_db():
    sql_config_path = os.path.join(PROJECT_ROOT, '..', 'config', 'sql.yaml')
    sql_conf = load_config(sql_path=sql_config_path)[0]

    # YOU NEED TO redo SQL_CONF path, or get database to accept somethign in a
    # higher directory

    sql_conf.database = os.path.join('..', sql_conf.database)

    db = Database(sql_conf.dialect, sql_conf.database, sql_conf.username,
                  sql_conf.password, sql_conf.host, sql_conf.port,
                  sql_conf.query)

    return db


def set_up_flask():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    api = Api(app, version='0.1', title='ATM API',
              description='A RESTful API for Auto Tuning Models')
    ns = api.namespace('api', description='ATM API operations')

    return (app, api, ns)


def object_as_dict(obj):
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}  # noqa


class JSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types, and
    UUIDs.
    See: https://stackoverflow.com/questions/11875770/how-to-overcome-datetime-datetime-not-json-serializable # noqa
    """

    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if o.utcoffset() is not None:
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            if o.microsecond:
                r = r[:12]
            return r
        elif isinstance(o, (decimal.Decimal, uuid.UUID)):
            return str(o)
        else:
            return super(JSONEncoder, self).default(o)


def encode_entity(entity=[]):
    """
    Creates a generic controller function to filter the entity by the value of
    one field.

    Uses simplejson (aliased to json) to parse Decimals and the custom
    JSONEncoder to parse datetime fields.
    """
    return json.dumps([object_as_dict(x) for x in entity], cls=JSONEncoder)



def get_operator_fn(op):
    return {
        '=' : operator.eq,
        '>' : operator.gt,
        'gt' : operator.gt,
        '>=' : operator.ge,
        'ge' : operator.ge,
        '<' : operator.lt,
        'lt' : operator.lt,
        '<=' : operator.le,
        'le' : operator.le,
        }.get(op, operator.eq)


db = set_up_db()
app, api, ns = set_up_flask()


dataset_parser = api.parser()
dataset_parser.add_argument('id', type=int, help='dataset identifier')
dataset_parser.add_argument('name', type=str, help='partial name')
dataset_parser.add_argument(
    'class_column', type=str, help='partial class column')
dataset_parser.add_argument('train_path', type=str, help='partial train_path')
dataset_parser.add_argument('test_path', type=str, help='partial test_path')
dataset_parser.add_argument(
    'description', type=str, help='partial description')
dataset_parser.add_argument('n_examples', type=int, help='number of examples')
dataset_parser.add_argument('k_classes', type=int, help='number of clases')
dataset_parser.add_argument(
    'd_features', type=int, help='number of d_features')
dataset_parser.add_argument('majority', type=float, help='majority')
dataset_parser.add_argument('size_kb', type=int, help='size in kb')

dataset_parser.add_argument(
    'n_examples_op', type=str, help='comparison operator. i.e. =, >, >=')


@ns.route('/datasets')
@api.expect(dataset_parser)
class Dataset(Resource):
    @ns.doc('get some or all datasets')
    def get(self):
        args = dataset_parser.parse_args()
        args['entity_id'] = args.get('id', None)
        args['n_examples_op'] = get_operator_fn(args.get('n_examples_op', None))
        args.pop('id', None)

        res = encode_entity(db.get_datasets(**args))
        return json.loads(res)


if __name__ == '__main__':
    app.run(debug=True)