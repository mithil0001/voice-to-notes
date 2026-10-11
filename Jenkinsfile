pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME       = "voice-to-notes"
        ACR_NAME         = "youracrname"
        ACR_LOGIN_SERVER = "${ACR_NAME}.azurecr.io"
        IMAGE_TAG        = "${env.BUILD_NUMBER}"
        FULL_IMAGE       = "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
        LATEST_IMAGE     = "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:latest"
        K8S_NAMESPACE    = "voice-to-notes"
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . venv/bin/activate
                    pytest --junitxml=test-results.xml
                '''
            }
            post {
                always { junit 'test-results.xml' }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${FULL_IMAGE} -t ${LATEST_IMAGE} ."
            }
        }

        stage('Publish to Azure Container Registry') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'acr-credentials',
                    usernameVariable: 'ACR_USERNAME',
                    passwordVariable: 'ACR_PASSWORD'
                )]) {
                    sh '''
                        echo "$ACR_PASSWORD" | docker login ${ACR_LOGIN_SERVER} -u "$ACR_USERNAME" --password-stdin
                        docker push ${FULL_IMAGE}
                        docker push ${LATEST_IMAGE}
                        docker logout ${ACR_LOGIN_SERVER}
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { return env.DEPLOY_TO_K8S != 'false' }
            }
            steps {
                withCredentials([
                    file(credentialsId: 'aks-kubeconfig', variable: 'KUBECONFIG_FILE'),
                    string(credentialsId: 'azure-speech-key', variable: 'AZURE_SPEECH_KEY'),
                    string(credentialsId: 'azure-speech-region', variable: 'AZURE_SPEECH_REGION')
                ]) {
                    sh '''
                        export KUBECONFIG=$KUBECONFIG_FILE

                        kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

                        kubectl create secret generic voice-to-notes-secrets \
                            --from-literal=AZURE_SPEECH_KEY=$AZURE_SPEECH_KEY \
                            --from-literal=AZURE_SPEECH_REGION=$AZURE_SPEECH_REGION \
                            --namespace ${K8S_NAMESPACE} \
                            --dry-run=client -o yaml | kubectl apply -f -

                        kubectl apply -f k8s/configmap.yaml -n ${K8S_NAMESPACE}
                        kubectl apply -f k8s/pvc.yaml -n ${K8S_NAMESPACE}
                        kubectl apply -f k8s/deployment.yaml -n ${K8S_NAMESPACE}
                        kubectl apply -f k8s/service.yaml -n ${K8S_NAMESPACE}

                        kubectl set image deployment/voice-to-notes voice-to-notes=${FULL_IMAGE} -n ${K8S_NAMESPACE}
                        kubectl rollout status deployment/voice-to-notes -n ${K8S_NAMESPACE} --timeout=120s
                    '''
                }
            }
        }
    }

    post {
        success { echo "Pipeline completed successfully. Image published: ${FULL_IMAGE}" }
        failure { echo "Pipeline failed. Review the failing stage log above." }
        always  { sh 'docker image prune -f || true' }
    }
}
