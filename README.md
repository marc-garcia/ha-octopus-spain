> **Security fork:** credential encryption with an external key. Read [SECURITY-FORK.md](SECURITY-FORK.md) before installing.

# Componente Octopus Spain para Home Assistant

## ¿Qué es Octopus Energy?

[Octopus Energy](https://octopusenergy.es/) es una comercializadora eléctrica española.

Entre otras ventajas, dispone de la **Solar Wallet**, un servicio que permite acumular crédito obtenido
por los excedentes solares para reducir a 0€ la factura así como acumular para posteriores facturas.

## ¿Qué hace el componente Octopus Spain?

Este componente conecta con tu cuenta de _Octopus Energy_ para obtener el estado actual de tu **Solar Wallet**
así como los datos básicos de última factura.

El proyecto original indica que fue revisado por Octopus Energy. **Los cambios de cifrado de este fork no han sido revisados ni aprobados por Octopus Energy.**

## Instalación de este fork

Antes de instalar, sigue [las instrucciones de clave externa y recuperación](SECURITY-FORK.md). Esta versión requiere un archivo de clave montado por separado; no funciona simplemente descargándola desde HACS. Conserva el dominio `octopus_spain` y sustituye a la integración original.

Repositorio: https://github.com/marc-garcia/ha-octopus-spain — rama `secure-credentials`.

## Configuración

Una vez instalado, ve a _Dispositivos y Servicios -> Añadir Integración_ y busca _Octopus_.

El asistente te solicitará tu email y contraseña de [Octopus Energy](https://octopusenergy.es/)

## Entidades

Una vez configurado el componente, tendrás dos entidades por cada cuenta que tengas asociada a tu email (normalmente una).

### Solar Wallet

La entidad Solar Wallet devuelve el valor actual de tu Solar Wallet. Este valor (en euros) estará actualizado al de tu última factura. Actualmente no se puede consultar en tiempo real.

## Octopus Credit

La entidad Octopus Credit devuelve el valor actual de tu crédito en Octopus obtenido por cuentas referedidas u otras posibles bonificaciones.

### Última Factura

Esta entidad devuelve el coste de tu última factura.

Adicionalmente, en los atributos, están disponibles las fechas de emisión de esa factura así el periodo (inicio y final) de la misma.

## Uso

Podrás usar estas etidades para visualizar el estado así como crear automatizaciones para informate, por ejemplo,
cuando se produzca un cambio en el atributo "Emitida" de última fáctura.

Una forma de representar los datos sería esta:

```yaml
title: Octopus Spain
type: entities
entities:
  - entity: sensor.ultima_factura_octopus
  - entity: sensor.solar_wallet
  - entity: sensor.octopus_credit
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Inicio
    icon: mdi:calendar-start
    attribute: Inicio
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Fin
    icon: mdi:calendar-end
    attribute: Fin
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Emitida
    icon: mdi:email-fast-outline
    attribute: Emitida
```

![card.png](img/card.png)

## Videotutorial

[![Octopus Spain](http://img.youtube.com/vi/fJ1W_wACbfw/0.jpg)](http://www.youtube.com/watch?v=fJ1W_wACbfw)
