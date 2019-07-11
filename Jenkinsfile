pipeline {
    agent any
    environment {

        //Get AWS region
        //Assume Jenkins is running on the same region as the cluster
        REGION =  sh(script:'curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region', returnStdout: true)
        STELLAR_ADDRESS = '$(aws ssm get-parameter --region $REGION --name /${Environment}/jenkins/STELLAR_ADDRESS | jq -r ".Parameter.Value")'
        STELLAR_BASE_SEED = '$(aws ssm get-parameter --region $REGION --name /${Environment}/jenkins/STELLAR_BASE_SEED | jq -r ".Parameter.Value")'
        CLUSTER_URL = '$(aws ssm get-parameter --region $REGION --name /${Environment}/jenkins/CLUSTER_URL | jq -r ".Parameter.Value")'
        //GIT_REVISION = sh (script : 'git rev-parse --short HEAD', returnStdout: true).trim()

    }

    stages {
        stage('Checkout') {
            steps {
                  git(
                       url: 'https://github.com/kinecosystem/payment-service.git',
                       branch: "${BRANCH}"
                   )
            }
        }
        stage ('Setup'){
            steps{
                script {
                    GIT_REVISION = sh (
                        script: "git rev-parse --short HEAD",
                        returnStdout: true
                    ).trim()
                }
                echo "Working on version: ${GIT_REVISION}"
             }
         }
         stage ('Code Quality'){
         //Todo: Quality and security plugins (FindBugs, CheckMarx, etc.)
            parallel {

                stage('Unit Test') {
                    steps {
                        echo 'Unit testing'
                        sh 'make test'
                    }
                }
                stage ('Code Quality'){
                    steps {
                        echo "Running codecov"
                        //todo: consider using sonarcube instead
                        sh 'pipenv run codecov'
                    }
                }
                stage('Create Docker Image') {
                    steps {
                        echo 'Creating docker image'
                        sh 'make build-image'
                    }
                }
            }
         }
        stage('Deploy to env') {
            steps {
                // get k8s environment

                script {
                    env['K8S_CLUSTER_URL'] = sh (
                            script: "echo $CLUSTER_URL",
                            returnStdout: true
                       ).trim()
                }
                echo "Deploying env to: $env.K8S_CLUSTER_URL"
                // Require to define the default2 (Kubernetes token) in Jenkins credentials
                withKubeConfig([credentialsId: 'default2',
                serverUrl: env.K8S_CLUSTER_URL,
                clusterName: 'test'
                ]) {
                    sh '''
                        #create namespace if doesn't exists
                        cat k8s/namespace.yaml | sed 's/__ENVIRONMENT'"/${Environment}/g" | kubectl apply -f - || true
                        GIT_REVISION=`git rev-parse --short HEAD`
                        SED_ARGS="s/__ENVIRONMENT/${Environment}/g; s/__ROLE/${Role}/g; s/__VERSION/${GIT_REVISION}/g; s/__DEBUG/${Debug}/g; s/__V3/-v3/g; s/__REPLICAS/${Replicas}/g"
                        cat k8s/payment-service-deployment.yaml \
                          | sed  "${SED_ARGS}" \
                          | kubectl apply  -f -
                     '''
                    }

            }
        }
        stage('Integration/System tests') {
            steps {
                echo 'Running Integration/System tests'
                //Todo: Extract logs and tests results to jenkins
                //Todo: Make sure the job runs only once
                withKubeConfig([credentialsId: 'default2',
                serverUrl: env.K8S_CLUSTER_URL,
                clusterName: 'test'
                ]) {
                    sh '''
                        GIT_REVISION=`git rev-parse --short HEAD`
                        #create namespace if doesn't exists
                        cat k8s/namespace.yaml | sed 's/__ENVIRONMENT'"/${Environment}/g" | kubectl apply -f - || true
                        SED_ARGS="s/__ENVIRONMENT/${Environment}/g; s/__SERVER_ROLE/${Role}/g; s/__VERSION/${GIT_REVISION}/g; s/__DEBUG/False/g;"
                        cat k8s/payment-service-test-deployment.yaml \
                          | sed  "${SED_ARGS}" \
                          | kubectl apply  -f -
                     '''
                    }
            }
        }
        stage('Push Docker image') {
            steps {
                echo 'Pushing Docker image to dockerhub'
                withDockerRegistry([ credentialsId: "dockerhub", url: "" ]) {
                    sh 'make push-image'
                }
            }
        }
    }
    post {
       // only triggered when blue or green sign
       success {
           slackSend ( color: '#00FF00', message: "SUCCESSFUL: '${env.JOB_NAME} [${env.BUILD_NUMBER}]' (${env.BUILD_URL})")
       }
       // triggered when red sign
       failure {
           slackSend (color: '#FF0000', message: "FAILED: '${env.JOB_NAME} [${env.BUILD_NUMBER}]' (${env.BUILD_URL})")
       }
    }
}
