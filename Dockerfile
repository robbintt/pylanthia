FROM ruby:latest as base

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# gtk2 no longer necessary in current lich? working fine without...
RUN gem install sqlite3

# use to profile with this guide: https://samsaffron.com/archive/2018/01/18/my-production-ruby-on-rails-cpu-is-at-100-now-what
# rbtrace -p 190 -e 'Thread.new{ require "stackprof"; StackProf.start(mode: :cpu); sleep 2; StackProf.stop; StackProf.results("/tmp/perf"); }'
# make sure you require rbtrace in lich.rb/lich.rbw
RUN gem install rbtrace
RUN gem install stackprof

# lazy setup dependencies, this could be more explicit for pyenv/pipenv
RUN apt-get update
RUN apt-get install -y python3-pip
RUN pip3 install pipenv

# this gets used to setup pipenv, then the volume shadows it
RUN mkdir /app
WORKDIR /app
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

# set up pyenv
ENV PYENV_ROOT /.pyenv
RUN curl https://pyenv.run | bash
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
# annoyingly, i haven't yet mounted the version specified in .python-version
RUN pyenv install 3.8.0

# set up pipenv
RUN pyenv exec pipenv sync
