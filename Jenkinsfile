pipeline {
  agent none
  environment {
    DOCKER_BUILDKIT = 1
  }
  stages {
    stage('geo-algo') {
      agent {
        dockerfile {
          filename 'docker/Dockerfile.build'
        }
      }
      steps {
        dir('geo-algo/VK-Aquifers') {
          sh 'cmake -DCMAKE_BUILD_TYPE=Release .'
          sh 'make'
          sh './viskar-geo-algo runTests'
        }
      }
    }
    stage('geocruncher & api') {
      agent {
        dockerfile {
          filename 'docker/Dockerfile.common'
        }
      }
      steps {
        withEnv(["HOME=${env.WORKSPACE}"]) {
          // TODO: Setuptools is deprecated and doesn't work anymore
          // replace with something else, then enable tests again
          // sh 'python geocruncher-setup.py test'
          sh 'python geocruncher-setup.py bdist_wheel'
          sh 'python api-setup.py bdist_wheel'
          // Apparently not needed since the files are already where we want them to be
          // sh 'cp dist/geocruncher-*.whl dist/'
          // sh 'cp dist/api-*.whl dist/'
        }
      }
    }
    stage('develop image') {
      agent any
      when { anyOf { branch 'develop' } }
      steps {
        sh 'docker build -t geocruncher/geocruncher-dev:$BUILD_NUMBER -t geocruncher/geocruncher-dev:latest -f docker/server.Dockerfile .'
        sh 'sudo systemctl restart geocruncher.dev'
        sh 'sudo systemctl status geocruncher.dev --no-pager -l'
      }
    }
    stage('master image') {
      agent any
      when { anyOf { branch 'master' } }
      steps {
        sh 'docker build -t geocruncher/geocruncher-prod:$BUILD_NUMBER -t geocruncher/geocruncher-prod:latest -f docker/server.Dockerfile .'
        sh 'sudo systemctl restart geocruncher.prod'
        sh 'sudo systemctl status geocruncher.prod --no-pager -l'
        sh 'docker image prune --filter "until=1440h" -f' // clean all unused images until 60 days ago
      }
    }
  }
}
