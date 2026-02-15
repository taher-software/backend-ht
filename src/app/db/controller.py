from abc import ABC
from src.app.db.orm import get_db
from src.app.globals.decorators import transactional


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

    def get_all(
        self,
        limit: int | None = None,
        namespace_id: int | None = None,
        offset: int | None = None,
        total: bool = False,
    ):
        data = self.db.query(self.resource).filter(
            self.resource.namespace_id == namespace_id
        )
        response = {}
        if offset:
            data = data.offset(offset)
        if limit:
            data = data.limit(limit)
        if total:
            total_count = data.count()
            response["total"] = total_count
        data = data.all()
        result = []
        for elt in data:
            result.append(elt.to_dict())
        response["items"] = result
        return response

    def create(self, metadata: dict, db, commit: bool = True, **kwargs):
        resource = self.resource(**metadata)
        db.add(resource)
        if commit:
            db.commit()
        else:
            db.flush()
        return resource.to_dict()

    def update(self, resource_id, metadata, resource_key="id", commit=True, **kwargs):
        db = kwargs["db"]
        row_data = db.query(self.resource).get(resource_id).to_dict()
        row_data.update(metadata)

        db.query(self.resource).filter(
            getattr(self.resource, resource_key) == resource_id
        ).update(metadata)
        db.commit() if commit else db.flush()
        return row_data

    def delete(self, resource_id, commit: bool = True, **kwargs):
        db = kwargs["db"]
        db.query(self.resource).filter(self.resource.id == resource_id).delete()
        if commit:
            db.commit()
        else:
            db.flush()
        return True

    def find_by_params(self, params: dict, **kwargs):
        db = kwargs["db"]
        query = db.query(self.resource)
        for key, value in params.items():
            query = query.filter(getattr(self.resource, key) == value)
        result = query.first()
        if not result:
            return None
        return result.to_dict()
