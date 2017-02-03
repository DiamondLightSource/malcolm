docs/html/index.html: $(wildcard docs/*.rst docs/conf.py)
	sphinx-build -b html docs docs/html

clean:
	rm -rf docs/html

