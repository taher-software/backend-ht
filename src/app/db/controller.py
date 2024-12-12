from abc import ABC
from app.db.orm import get_db
from app.globals.decorators import transactional


class DbControllerInterface(ABC):
    def find_by_id(self, resource_id):
        pass

    def find_by_field():
        pass

    def get_all(self, limit: int):
        pass

    def create(self, metadata):
        pass

    def update(self, resource_id, metadata):
        pass

    def delete(self, resource_id):
        pass


class dbController(DbControllerInterface):
    def __init__(self, resource) -> None:
        self.resource = resource
        db_session = get_db()
        self.db = next(db_session)

    def find_by_id(self, resource_id):
        result = self.db.query(self.resource).get(resource_id)
        if result:
            return result.to_dict()
        return None

    def find_by_field(self, field, field_value, all=None):
        if all:
            result = (
                self.db.query(self.resource)
                .filter(getattr(self.resource, field) == field_value)
                .all()
            )
            return result.to_dict()

        result = (
            self.db.query(self.resource)
            .filter(getattr(self.resource, field) == field_value)
            .first()
        )
        if not result:
            return None
        payload = result.to_dict()
        return payload

    def get_all(self, limit: int | None = None):
        if limit:
            data = self.db.query(self.resource).limit(limit).all()
        else:
            data = self.db.query(self.resource).all()

        result = []
        for elt in data:
            result.append(elt.to_dict())
        return result

    @transactional
    def create(self, metadata: dict, db):
        resource = self.resource(**metadata)
        db.add(resource)
        return metadata

    @transactional
    def update(self, resource_id, metadata, resource_key="id", **kwargs):
        db = kwargs["db"]
        row_data = db.query(self.resource).get(resource_id).to_dict()
        row_data.update(metadata)

        db.query(self.resource).filter(
            getattr(self.resource, resource_key) == resource_id
        ).update(metadata)
        return row_data

    @transactional
    def delete(self, resource_id, **kwargs):
        db = kwargs["db"]
        db.query(self.resource).filter(self.resource.id == resource_id).delete()
