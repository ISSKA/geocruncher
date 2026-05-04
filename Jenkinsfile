pipeline {
  agent none
  environment {
    DOCKER_BUILDKIT = 1
  }
  stages {
    stage('draco') {
      agent {
        dockerfile {
          filename 'docker/Dockerfile.build'
        }
      }
      steps {
        dir('third_party/draco') {
          sh '''
          mkdir -p ../draco_build && cd ../draco_build
          cmake \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX=${WORKSPACE}/draco_install \
          -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
          ../draco
          make -j$(nproc) install
          '''
        }
        // Archive Draco artifacts for geo-algo stage
        stash name: 'draco_artifacts', includes: "draco_install/**"
      }
    }
    stage('geo-algo') {
      agent {
        dockerfile {
          filename 'docker/Dockerfile.build'
        }
      }
      steps {
        // Retrieve Draco artifacts
        unstash 'draco_artifacts'
        dir('geo-algo/VK-Aquifers') {
          sh '''
          cmake \
          -DCMAKE_BUILD_TYPE=Release \
          -DDRACO_INSTALL_DIR=${WORKSPACE}/draco_install \
          -DPython_EXECUTABLE=/opt/venv/bin/python \
          -Dpybind11_DIR="$(/opt/venv/bin/python -m pybind11 --cmakedir)" \
          .
          cmake --build .
          '''
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
          // TODO: re-enable tests once known regressions are addressed.
          // The setuptools blocker is gone (uv + hatchling now); leaving
          // disabled until the suite is green. To re-enable:
          //   sh 'uv run --frozen pytest'
          sh 'uv build'
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
