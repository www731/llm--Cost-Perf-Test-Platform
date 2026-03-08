/**
 * LLM性能测试平台 Jenkins Pipeline
 * 支持DeepSeek API和Ollama本地模型测试
 */

pipeline {
    agent {
        docker {
            image 'jenkins/jnlp-agent-python:latest'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    environment {
        // 从Jenkins凭据获取
        DEEPSEEK_API_KEY = credentials('deepseek-api-key')

        // 数据库配置
        DB_HOST = 'mysql'
        DB_USER = 'tester'
        DB_PASSWORD = 'test123'
        DB_NAME = 'llm_perf'
    }

    parameters {
        choice(
            name: 'TEST_TARGET',
            choices: ['api', 'ollama', 'both'],
            description: '测试目标'
        )
        string(
            name: 'CONCURRENT_USERS',
            defaultValue: '20',
            description: '并发用户数'
        )
        string(
            name: 'TEST_DURATION',
            defaultValue: '300',
            description: '测试时长(秒)'
        )
        string(
            name: 'BUDGET_LIMIT',
            defaultValue: '1.0',
            description: '预算限制(美元)'
        )
        choice(
            name: 'MODEL_API',
            choices: ['deepseek-chat', 'deepseek-coder'],
            description: 'DeepSeek API模型'
        )
        choice(
            name: 'MODEL_OLLAMA',
            choices: ['deepseek-r1:1.5b', 'deepseek-r1:7b'],
            description: 'Ollama本地模型'
        )
        booleanParam(
            name: 'SAVE_TO_DB',
            defaultValue: true,
            description: '保存结果到数据库'
        )
    }

    stages {
        stage('环境准备') {
            steps {
                script {
                    sh '''
                        echo "🔧 环境准备..."
                        python --version
                        pip install -r requirements.txt
                        docker --version
                        docker-compose --version
                    '''
                }
            }
        }

        stage('启动服务') {
            when {
                expression { params.TEST_TARGET == 'ollama' || params.TEST_TARGET == 'both' }
            }
            steps {
                script {
                    sh '''
                        echo "🚀 启动Ollama服务..."
                        cd docker
                        docker-compose up -d ollama mysql
                        sleep 30  # 等待服务启动

                        # 检查Ollama状态
                        curl -s http://localhost:11434/api/tags || echo "Ollama未就绪"
                    '''
                }
            }
        }

        stage('运行API测试') {
            when {
                expression { params.TEST_TARGET == 'api' || params.TEST_TARGET == 'both' }
            }
            steps {
                script {
                    sh '''
                        echo "🌐 运行DeepSeek API测试..."
                        cd jmeter
                        chmod +x run_test.sh

                        # 设置API密钥
                        export DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}

                        # 运行测试
                        ./run_test.sh \
                            --target=api \
                            --users=${CONCURRENT_USERS} \
                            --duration=${TEST_DURATION} \
                            --model=${MODEL_API} \
                            --budget=${BUDGET_LIMIT}
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'results/jtl/*.jtl, results/reports/**', fingerprint: true
                    junit 'results/summary/*.xml'  // 如果有JUnit格式
                }
                failure {
                    echo "❌ API测试失败"
                }
            }
        }

        stage('运行Ollama测试') {
            when {
                expression { params.TEST_TARGET == 'ollama' || params.TEST_TARGET == 'both' }
            }
            steps {
                script {
                    sh '''
                        echo "💻 运行Ollama本地测试..."
                        cd jmeter

                        ./run_test.sh \
                            --target=ollama \
                            --users=${CONCURRENT_USERS} \
                            --duration=${TEST_DURATION} \
                            --model=${MODEL_OLLAMA} \
                            --budget=${BUDGET_LIMIT}
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'results/jtl/*.jtl, results/reports/**', fingerprint: true
                }
            }
        }

        stage('模型对比分析') {
            when {
                expression { params.TEST_TARGET == 'both' }
            }
            steps {
                script {
                    sh '''
                        echo "📊 执行模型对比分析..."
                        python scripts/compare_models.py
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'compare-*.png', fingerprint: true
                }
            }
        }

        stage('成本控制检查') {
            steps {
                script {
                    sh '''
                        echo "💰 检查预算执行情况..."
                        python scripts/check_budget.py
                    '''
                }
            }
        }

        stage('生成最终报告') {
            steps {
                script {
                    sh '''
                        echo "📈 生成最终报告..."
                        python scripts/generate_report.py
                    '''
                }
            }
            post {
                always {
                    publishHTML([
                        reportDir: 'results/reports',
                        reportFiles: 'index.html',
                        reportName: 'LLM性能测试报告'
                    ])
                }
            }
        }
    }

    post {
        always {
            script {
                sh '''
                    echo "🧹 清理环境..."
                    cd docker
                    docker-compose down || true
                '''
            }
            cleanWs()
        }
        success {
            echo "✅ 所有测试通过！"
            emoji ':+1:'
        }
        failure {
            echo "❌ 测试失败，请检查日志"
            emoji ':x:'
            // 发送邮件通知
            mail to: 'team@example.com',
                 subject: "Jenkins Pipeline Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                 body: "请检查构建结果: ${env.BUILD_URL}"
        }
        unstable {
            echo "⚠️ 测试不稳定，可能需要检查"
        }
        aborted {
            echo "🛑 构建被中止"
        }
    }
}