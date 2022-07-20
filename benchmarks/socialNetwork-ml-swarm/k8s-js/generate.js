#!/usr/bin/env node
'use strict';

const worker1 = 'autosys-12';
const worker2 = 'autosys-12';
const image_cpp = 'yz2297/social-network-ml-swarm';
const image_nginx = 'yg397/openresty-thrift:xenial';
const app_path = '/home/pingheli/sinan-local/benchmarks/socialNetwork-ml-swarm/'

const dnsmasq = {
  name: 'dnsmasq',
  image: 'janeczku/go-dnsmasq:release-1.0.7@sha256:3a99ad92353b55e97863812470e4f7403b47180f06845fdd06060773fe04184f',
  args: [
    '--listen',
    '127.0.0.1:53',
    '--default-resolver',
    '--append-search-domains',
  ],
};

function labels(name) {
  return {
    deathStarProject: 'social-network',
    appName: name,
  };
}

function env(o) {
  return Object.entries(o).map(([name, value]) => ({name, value}));
}

function deployment(name, {nodeName, containers, volumes}) {
  return {
    apiVersion: 'apps/v1',
    kind: 'Deployment',
    metadata: {
      namespace: 'social-network-ml',
      name,
      labels: labels(name),
    },
    spec: {
      replicas: 1,
      selector: {
        matchLabels: labels(name),
      },
      template: {
        metadata: {
          name,
          labels: labels(name),
        },
        spec: {
          nodeName,
          containers,
          volumes,
          restartPolicy: 'Always',
          enableServiceLinks: false,
        },
      },
    },
  };
}

function service(name, {serviceType, ports}) {
  return {
    apiVersion: 'v1',
    kind: 'Service',
    metadata: {
      namespace: 'social-network-ml',
      name,
      labels: labels(name),
    },
    spec: {
      type: serviceType,
      ports,
      selector: labels(name),
    },
  };
}

function deployment_service(name, {nodeName, containers, volumes, serviceType, ports}) {
  return [
    deployment(name, {nodeName, containers, volumes}),
    service(name, {serviceType, ports}),
  ];
}

function cpp(name, command) {
  return deployment_service(name, {
    nodeName: worker1,
    containers: [
      {
        name,
        image: image_cpp,
        command: [command],
        volumeMounts: [
          {
            mountPath: '/social-network-microservices/config',
            name: 'config',
          },
        ],
      },
    ],
    volumes: [
      {
        name: 'config',
        hostPath: {
          path: app_path + './config',
          type: 'Directory',
        },
      },
    ],
    ports: [
      {port: 9090},
    ],
  });
}

function memcached(name) {
  return deployment_service(name, {
    nodeName: worker1,
    containers: [
      {
        name,
        image: 'memcached:1.6.0',
        env: env({
          MEMCACHED_CACHE_SIZE: '4096',
          MEMCACHED_THREADS: '8',
        }),
      },
    ],
    ports: [
      {port: 11211},
    ],
  });
}

function mongodb(name) {
  return deployment_service(name, {
    nodeName: worker1,
    containers: [
      {
        name,
        image: 'mongo',
        args: [
          '--nojournal',
          '--quiet',
        ],
      },
    ],
    ports: [
      {port: 27017},
    ],
  });
}

function redis(name) {
  return deployment_service(name, {
    nodeName: worker1,
    containers: [
      {
        name,
        image: 'redis',
        command: ['sh', '-c', 'rm -f /data/dump.rdb && redis-server --save \"\" --appendonly no'],
      },
    ],
    ports: [
      {port: 6379},
    ],
  });
}

function rabbitmq(name, cookie) {
  return deployment_service(name, {
    nodeName: worker1,
    containers: [
      {
        name,
        image: 'rabbitmq',
        env: env({
          RABBITMQ_ERLANG_COOKIE: cookie,
          RABBITMQ_DEFAULT_VHOST: '/',
        }),
      },
    ],
    ports: [
      {port: 5672},
    ],
  });
}

const doc = {
  apiVersion: 'v1',
  kind: 'List',
  items: [

    {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'social-network-ml',
        labels: {
          deathStarProject: 'social-network',
        },
      },
    },

    ...deployment_service('jaeger', {
      nodeName: worker2,
      containers: [
        {
          name: 'jaeger',
          image: 'jaegertracing/all-in-one:latest',
          env: env({
            COLLECTOR_ZIPKIN_HTTP_PORT: '9411',
          }),
        },
      ],
      serviceType: 'NodePort',
      ports: [
        {name: '16686', port: 16686, nodePort: 30005},
        {name: '9411', port: 9411},
      ],
    }),

    ...deployment_service('nginx-thrift', {
      nodeName: worker1,
      containers: [
        {
          name: 'nginx-thrift',
          image: image_nginx,
          volumeMounts: [
            {
              mountPath: '/usr/local/openresty/nginx/lua-scripts',
              name: 'lua-scripts',
            },
            {
              mountPath: '/usr/local/openresty/nginx/pages',
              name: 'pages',
            },
            {
              mountPath: '/usr/local/openresty/nginx/conf/nginx.conf',
              name: 'nginx-conf',
            },
            {
              mountPath: '/usr/local/openresty/nginx/jaeger-config.json',
              name: 'jaeger-config-json',
            },
            {
              mountPath: '/gen-lua',
              name: 'gen-lua',
            },
          ],
        },
        dnsmasq,
      ],
      volumes: [
        {
          name: 'lua-scripts',
          hostPath: {
            path: app_path + './nginx-web-server/lua-scripts',
            type: 'Directory',
          },
        },
        {
          name: 'pages',
          hostPath: {
            path: app_path + './nginx-web-server/pages',
            type: 'Directory',
          },
        },
        {
          name: 'nginx-conf',
          hostPath: {
            path: app_path + './nginx-web-server/conf/nginx-k8s.conf',
            type: 'File',
          },
        },
        {
          name: 'jaeger-config-json',
          hostPath: {
            path: app_path + './nginx-web-server/jaeger-config.json',
            type: 'File',
          },
        },
        {
          name: 'gen-lua',
          hostPath: {
            path: app_path + './gen-lua',
            type: 'Directory',
          },
        },
      ],
      serviceType: 'NodePort',
      ports: [
        {port: 8080, nodePort: 30001},
      ],
    }),

    ...cpp('compose-post-service', 'ComposePostService'),
    ...redis('compose-post-redis'),

    ...cpp('home-timeline-service', 'HomeTimelineService'),
    ...redis('home-timeline-redis'),

    ...cpp('media-service', 'MediaService'),

    ...cpp('post-storage-service', 'PostStorageService'),
    ...memcached('post-storage-memcached'),
    ...mongodb('post-storage-mongodb'),

    ...cpp('social-graph-service', 'SocialGraphService'),
    ...mongodb('social-graph-mongodb'),
    ...redis('social-graph-redis'),

    ...cpp('text-service', 'TextService'),

    ...cpp('unique-id-service', 'UniqueIdService'),

    ...cpp('url-shorten-service', 'UrlShortenService'),

    ...cpp('user-mention-service', 'UserMentionService'),

    ...cpp('user-service', 'UserService'),
    ...memcached('user-memcached'),
    ...mongodb('user-mongodb'),

    ...cpp('user-timeline-service', 'UserTimelineService'),
    ...mongodb('user-timeline-mongodb'),
    ...redis('user-timeline-redis'),

    ...cpp('write-home-timeline-service', 'WriteHomeTimelineService'),
    ...rabbitmq('write-home-timeline-rabbitmq', 'WRITE-HOME-TIMELINE-RABBITMQ'),

    ...cpp('write-user-timeline-service', 'WriteUserTimelineService'),
    ...rabbitmq('write-user-timeline-rabbitmq', 'WRITE-USER-TIMELINE-RABBITMQ'),

    ...deployment_service('media-filter-service', {
      nodeName: worker1,
      containers: [
        {
          name: 'media-filter-service',
          image: 'yz2297/social-network-media-filter',
          volumeMounts: [
            {
              mountPath: '/social-network-microservices/config',
              name: 'config',
            },
          ],
        },
      ],
      volumes: [
        {
          name: 'config',
          hostPath: {
            path: app_path + './config-py',
            type: 'Directory',
          },
        },
      ],
      ports: [
        {port: 40000},
      ],
    }),

    ...deployment_service('text-filter-service', {
      nodeName: worker1,
      containers: [
        {
          name: 'text-filter-service',
          image: 'yz2297/social-network-text-filter',
          volumeMounts: [
            {
              mountPath: '/social-network-microservices/config',
              name: 'config',
            },
          ],
        },
      ],
      volumes: [
        {
          name: 'config',
          hostPath: {
            path: app_path + './config-py',
            type: 'Directory',
          },
        },
      ],
      ports: [
        {port: 40000},
      ],
    }),

  ],
};

process.stdout.write(JSON.stringify(doc, null, 2) + '\n')
