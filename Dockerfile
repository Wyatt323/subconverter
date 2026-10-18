FROM debian:trixie-slim AS builder
ARG DEBIAN_FRONTEND=noninteractive
ARG THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git g++ make cmake pkg-config libcurl4-openssl-dev rapidjson-dev libpcre2-dev libyaml-cpp-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN git clone https://github.com/ftk/quickjspp.git && cd quickjspp && git checkout 0c00c48895919fc02da3f191a2da06addeb07f09 && git submodule update --init && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target quickjs -j ${THREADS} && install -d /usr/local/lib/quickjs /usr/local/include/quickjs && install -m644 build/quickjs/libquickjs.a /usr/local/lib/quickjs/ && install -m644 quickjs/quickjs.h quickjs/quickjs-libc.h /usr/local/include/quickjs/
RUN git clone https://github.com/PerMalmberg/libcron.git && cd libcron && git checkout ee34810b11bd23c8be637345532f91059b68b2d7 && git submodule update --init && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target libcron -j ${THREADS} && install -m644 libcron/out/Release/liblibcron.a /usr/local/lib/ && cp -r libcron/include/libcron /usr/local/include/ && cp -r libcron/externals/date/include/date /usr/local/include/
RUN git clone --depth 1 --branch v4.3.0 https://github.com/ToruNiina/toml11.git && cmake -S toml11 -B toml-build && cmake --install toml-build
COPY . /src
RUN cmake -S /src -B /build/app -DCMAKE_BUILD_TYPE=Release && cmake --build /build/app -j ${THREADS} && strip /build/app/subconverter

FROM debian:trixie-slim
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/Wyatt323/subconverter" org.opencontainers.image.revision="${VCS_REF}"
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl libyaml-cpp0.8 libpcre2-8-0 tzdata && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/app/subconverter /usr/local/bin/subconverter
COPY base/ /usr/share/subconverter/defaults/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENV TZ=Asia/Shanghai
WORKDIR /base
VOLUME ["/base"]
EXPOSE 25500
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD curl -fsS http://127.0.0.1:25500/version || exit 1
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["subconverter"]
