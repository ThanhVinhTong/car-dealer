FROM apify/actor-python-playwright:3.13

COPY --chown=myuser:myuser .actor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=myuser:myuser app ./app

CMD ["python", "-m", "app.apify_main"]