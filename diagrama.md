graph TD;
  A[Django Admin] -->|Trigger| B(Celery Worker);
  B --> C{Generar HTML};
